"""Session lifecycle service.

All session mutations go through this service so billing + realtime stays
consistent. The backend is the single source of truth for time (requirement #42).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Session,
    SessionStatus,
    SessionType,
    Station,
    Tariff,
    Transaction,
)
from app.services.billing import calculate_fixed_price, calculate_open_price


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(dt: datetime | None) -> datetime | None:
    """Normalize ORM-read datetimes to tz-aware UTC (SQLite may return naive)."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


async def get_persistable_session(db: AsyncSession, session_id: int) -> Session:
    session = await db.get(Session, session_id)
    if session is None:
        raise ValueError("Session not found")
    return session


async def get_free_station(db: AsyncSession, station_id: int) -> Station:
    station = await db.get(Station, station_id)
    if station is None:
        raise ValueError("Station not found")
    if not station.is_active:
        raise ValueError("Station is disabled")
    return station


async def station_has_active_session(db: AsyncSession, station_id: int) -> Optional[Session]:
    # EXPIRED counts as occupied: a finished fixed session must be settled
    # (stopped by the admin) or extended before the station frees up.
    stmt = select(Session).where(
        Session.station_id == station_id,
        Session.status.in_(
            [
                SessionStatus.ACTIVE,
                SessionStatus.OPEN,
                SessionStatus.PAUSED,
                SessionStatus.EXPIRED,
            ]
        ),
    )
    return await db.scalar(stmt)


async def create_session(
    db: AsyncSession,
    station_id: int,
    tariff: Tariff,
    is_open: bool = False,
    duration_minutes: Optional[int] = None,
) -> Session:
    """Create a FIXED or OPEN session."""

    now = utcnow()

    if is_open:
        session_type, session_status = SessionType.OPEN, SessionStatus.OPEN
        expires_at = None
        duration = 0
    else:
        if duration_minutes is None or duration_minutes <= 0:
            raise ValueError("Fixed sessions require duration_minutes > 0")
        session_type, session_status = SessionType.FIXED, SessionStatus.ACTIVE
        expires_at = now + timedelta(minutes=duration_minutes)
        duration = duration_minutes

    station = await get_free_station(db, station_id)
    if await station_has_active_session(db, station_id):
        raise ValueError(f"Station {station.name} already has an active session")

    session = Session(
        station_id=station.id,
        tariff_id=tariff.id,
        type=session_type,
        status=session_status,
        started_at=now,
        expires_at=expires_at,
        price_snapshot=tariff.price_per_hour,
        amount=None,
    )
    db.add(session)
    await db.flush()
    return session


async def extend_session(
    db: AsyncSession, session: Session, duration_minutes: int
) -> Session:
    """Extend a FIXED session (also revives an EXPIRED one)."""
    if session.type != SessionType.FIXED:
        raise ValueError("Only fixed sessions can be extended")
    if session.status == SessionStatus.COMPLETED:
        raise ValueError("Session already completed")

    base = session.expires_at or utcnow()
    session.expires_at = base + timedelta(minutes=duration_minutes)

    if session.status == SessionStatus.EXPIRED:
        session.status = SessionStatus.ACTIVE
    if session.status == SessionStatus.PAUSED:
        session.paused_at = None

    # a new final time means warnings must be re-armed
    session.warning_5_sent = False
    session.warning_3_sent = False
    session.warning_1_sent = False
    session.expired_sent = False
    await db.flush()
    return session


async def extend_session_free(
    db: AsyncSession, session: Session, duration_minutes: int
) -> Session:
    """Add free (unbilled) minutes to a FIXED session.

    The timer is pushed forward and the same span is recorded in
    ``comp_seconds`` so ``fixed_session_price`` stays unchanged. Used to
    compensate clients for outages. Revives an EXPIRED session.
    """
    if session.type != SessionType.FIXED:
        raise ValueError("Only fixed sessions can be extended")
    if session.status == SessionStatus.COMPLETED:
        raise ValueError("Session already completed")
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be > 0")

    seconds = duration_minutes * 60
    base = as_aware(session.expires_at) or utcnow()
    session.expires_at = base + timedelta(seconds=seconds)
    session.comp_seconds = (session.comp_seconds or 0) + seconds

    if session.status == SessionStatus.EXPIRED:
        session.status = SessionStatus.ACTIVE

    # a new final time means warnings must be re-armed
    session.warning_5_sent = False
    session.warning_3_sent = False
    session.warning_1_sent = False
    session.expired_sent = False
    await db.flush()
    return session


async def pause_session(db: AsyncSession, session: Session) -> Session:
    """Pause an ACTIVE/OPEN session."""
    if session.status not in (SessionStatus.ACTIVE, SessionStatus.OPEN):
        raise ValueError(f"Session is not running (status={session.status})")
    if session.paused_at is not None:
        raise ValueError("Session is already paused")
    session.paused_at = utcnow()
    session.status = SessionStatus.PAUSED
    await db.flush()
    return session


async def resume_session(db: AsyncSession, session: Session) -> Session:
    """Resume a PAUSED session."""
    if session.status != SessionStatus.PAUSED or session.paused_at is None:
        raise ValueError("Session is not paused")
    now = utcnow()
    paused_for = (now - as_aware(session.paused_at)).total_seconds()
    session.total_paused_seconds += int(paused_for)
    session.paused_at = None
    if session.type == SessionType.FIXED and session.expires_at is not None:
        session.expires_at += timedelta(seconds=paused_for)
    session.status = (
        SessionStatus.ACTIVE
        if session.type == SessionType.FIXED
        else SessionStatus.OPEN
    )
    await db.flush()
    return session


async def check_and_expire_fixed_sessions(db: AsyncSession) -> list[Session]:
    """Roll all overdue FIXED sessions into EXPIRED. Returns the changed rows.

    Comparison is done in Python (UTC-aware) so SQLite test envs behave the
    same as PostgreSQL.
    """
    now = utcnow()
    stmt = select(Session).where(
        Session.type == SessionType.FIXED,
        Session.status == SessionStatus.ACTIVE,
        Session.expires_at.is_not(None),
    )
    rows = (await db.scalars(stmt)).all()
    changed = []
    for s in rows:
        exp = as_aware(s.expires_at)
        if exp is not None and exp <= now:
            s.status = SessionStatus.EXPIRED
            changed.append(s)
    if changed:
        await db.flush()
    return list(changed)


def fixed_session_price(
    session: Session,
) -> Decimal:
    """The fixed price for a FIXED session (from purchased duration).

    Paused and free/compensated time shift ``expires_at`` but were never
    purchased, so they are excluded from the billable minutes.
    """
    if session.type != SessionType.FIXED:
        raise ValueError("Not a fixed session")
    if session.expires_at is None:
        raise ValueError("Fixed session missing expires_at")
    span = (as_aware(session.expires_at) - as_aware(session.started_at)).total_seconds()
    span -= session.total_paused_seconds or 0
    span -= session.comp_seconds or 0
    minutes = int(max(span, 0) // 60)
    return calculate_fixed_price(minutes, session.price_snapshot)


def open_session_current_price(
    session: Session,
    now: datetime | None = None,
) -> Decimal:
    """Live price for an OPEN session (shown on TV, final on stop).

    Exact to the second: price_per_hour / 3600 * elapsed_seconds."""
    now = now or utcnow()
    elapsed_seconds = (now - as_aware(session.started_at)).total_seconds()
    elapsed_seconds = max(elapsed_seconds - session.total_paused_seconds, 0.0)
    if session.status == SessionStatus.PAUSED and session.paused_at is not None:
        # exclude the currently-paused slice
        paused_so_far = (now - as_aware(session.paused_at)).total_seconds()
        elapsed_seconds = max(elapsed_seconds - paused_so_far, 0.0)
    return calculate_open_price(elapsed_seconds, session.price_snapshot)


async def stop_session(
    db: AsyncSession, session: Session
) -> tuple[Session, Decimal]:
    """Stop an ACTIVE/OPEN/PAUSED/EXPIRED session: compute final price, create a
    transaction, mark COMPLETED and release the station."""
    if session.status == SessionStatus.COMPLETED:
        raise ValueError("Session already completed")

    now = utcnow()

    # close out any running pause
    if session.status == SessionStatus.PAUSED and session.paused_at is not None:
        paused_for = (now - as_aware(session.paused_at)).total_seconds()
        session.total_paused_seconds += int(paused_for)
        session.paused_at = None

    if session.type == SessionType.FIXED:
        amount: Decimal = session.amount or fixed_session_price(session)
    else:
        amount = open_session_current_price(session, now)

    session.status = SessionStatus.COMPLETED
    session.ended_at = now
    session.amount = amount

    transaction = Transaction(
        session_id=session.id,
        amount=amount,
    )
    db.add(transaction)
    await db.flush()
    return session, amount

async def list_active(db: AsyncSession) -> list[Session]:
    """All sessions currently occupying a station (ACTIVE/OPEN/PAUSED/EXPIRED)."""
    stmt = (
        select(Session)
        .where(
            Session.status.in_(
                [
                    SessionStatus.ACTIVE,
                    SessionStatus.OPEN,
                    SessionStatus.PAUSED,
                    SessionStatus.EXPIRED,
                ]
            )
        )
        .order_by(Session.started_at.desc())
    )
    return list((await db.scalars(stmt)).all())


# ── bulk actions (power-outage helpers) ──────────────────────────────────────
async def pause_all_sessions(db: AsyncSession) -> list[Session]:
    """Pause every running (ACTIVE/OPEN) session. Returns the affected rows."""
    rows = (
        await db.scalars(
            select(Session).where(
                Session.status.in_([SessionStatus.ACTIVE, SessionStatus.OPEN])
            )
        )
    ).all()
    affected: list[Session] = []
    for session in rows:
        try:
            affected.append(await pause_session(db, session))
        except ValueError:
            continue
    return affected


async def resume_all_sessions(db: AsyncSession) -> list[Session]:
    """Resume every PAUSED session. Returns the affected rows."""
    rows = (
        await db.scalars(
            select(Session).where(Session.status == SessionStatus.PAUSED)
        )
    ).all()
    affected: list[Session] = []
    for session in rows:
        try:
            affected.append(await resume_session(db, session))
        except ValueError:
            continue
    return affected


async def extend_all_free(db: AsyncSession, duration_minutes: int) -> list[Session]:
    """Add free (unbilled) minutes to every FIXED session still occupying a
    station. OPEN sessions are ignored. Returns the affected rows."""
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be > 0")
    rows = (
        await db.scalars(
            select(Session).where(
                Session.type == SessionType.FIXED,
                Session.status.in_(
                    [
                        SessionStatus.ACTIVE,
                        SessionStatus.PAUSED,
                        SessionStatus.EXPIRED,
                    ]
                ),
            )
        )
    ).all()
    affected: list[Session] = []
    for session in rows:
        try:
            affected.append(
                await extend_session_free(db, session, duration_minutes)
            )
        except ValueError:
            continue
    return affected
