"""Dashboard builder: produces the TV/admindashboard snapshot (realtime)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    ClubSettings,
    Session,
    SessionStatus,
    SessionType,
    Station,
)
from app.schemas.schemas import DashboardResponse, StationState
from app.services.session_service import (
    fixed_session_price,
    open_session_current_price,
    utcnow,
)


def _station_state(
    station: Station,
    session: Optional[Session],
    now: datetime,
) -> StationState:
    state = StationState(
        id=station.id,
        name=station.name,
        number=station.number,
        type=station.type,
        is_active=station.is_active,
        total_paused_seconds=0,
    )
    if session is not None:
        state.session_id = session.id
        state.session_type = session.type
        state.status = session.status
        state.started_at = session.started_at
        state.expires_at = session.expires_at
        state.paused_at = session.paused_at
        state.total_paused_seconds = session.total_paused_seconds
        state.price_snapshot = session.price_snapshot
        state.warning_5_sent = session.warning_5_sent
        state.warning_3_sent = session.warning_3_sent
        state.warning_1_sent = session.warning_1_sent
        state.expired_sent = session.expired_sent

        if session.type == SessionType.OPEN:
            state.amount = open_session_current_price(session, now)
        elif session.type == SessionType.FIXED:
            state.amount = session.amount or fixed_session_price(session)
    return state


async def build_dashboard(db: AsyncSession) -> DashboardResponse:
    """Build a full dashboard snapshot from the DB (server-time is truth)."""
    now = utcnow()

    # Server is source of truth: flip overdue FIXED sessions to EXPIRED now.
    from app.services.session_service import check_and_expire_fixed_sessions

    changed = await check_and_expire_fixed_sessions(db)
    if changed:
        # Persist the EXPIRED transition so it survives this request/session.
        await db.commit()

    settings = await db.scalar(select(ClubSettings).order_by(ClubSettings.id))
    stations = (
        await db.scalars(select(Station).order_by(Station.number))
    ).all()

    # Grab all occupying sessions in one query. EXPIRED is included so a
    # finished-but-unsettled fixed session keeps showing on the board until the
    # admin stops or extends it (station stays occupied, not "free").
    session_map: dict[int, Session] = {}
    active = (
        await db.scalars(
            select(Session)
            .options(selectinload(Session.tariff))
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
        )
    ).all()
    for s in active:
        session_map[s.station_id] = s

    states = [
        _station_state(st, session_map.get(st.id), now)
        for st in stations
        if st.is_active
    ]

    voice_enabled = settings.voice_enabled if settings else True
    club_name = settings.club_name if settings else "PLAYSTATION CLUB"
    currency = settings.currency if settings else "KGS"

    return DashboardResponse(
        club_name=club_name,
        currency=currency,
        voice_enabled=voice_enabled,
        server_time=now,
        stations=states,
    )
