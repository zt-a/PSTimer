"""Analytics & reporting service.

All aggregation happens in Python after filtering in SQL. This keeps the queries
portable between PostgreSQL (production) and SQLite (tests) and is more than
fast enough for a club with <= a few thousand sessions per retention window.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.timeutils import as_aware, to_local, utcnow
from app.models import (
    Session,
    SessionStatus,
    Station,
    Transaction,
)
from app.schemas.schemas import (
    CleanupResult,
    HeatmapCell,
    PaymentItem,
    PaymentPage,
    PeriodSummary,
    RevenueSeries,
    SeriesPoint,
    SessionHistoryItem,
    SessionHistoryPage,
    StationStat,
    TariffStat,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def _play_seconds(session: Session) -> int:
    if not session.started_at or not session.ended_at:
        return 0
    elapsed = int(
        (as_aware(session.ended_at) - as_aware(session.started_at)).total_seconds()
    )
    return max(elapsed - (session.total_paused_seconds or 0), 0)


def _duration_minutes(session: Session) -> int:
    return _play_seconds(session) // 60


def _delta(current: float, previous: float) -> Optional[float]:
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


async def _completed_sessions(
    db: AsyncSession, start: datetime, end: datetime
) -> list[Session]:
    rows = await db.scalars(
        select(Session)
        .where(
            Session.status == SessionStatus.COMPLETED,
            Session.ended_at.is_not(None),
            Session.ended_at >= start,
            Session.ended_at < end,
        )
        .options(selectinload(Session.station), selectinload(Session.tariff))
    )
    return list(rows)


async def _active_station_count(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(Station).where(Station.is_active.is_(True))
        )
        or 0
    )


def pick_bucket(start: datetime, end: datetime) -> str:
    days = (end - start).total_seconds() / 86400
    if days <= 2:
        return "hour"
    if days <= 70:
        return "day"
    if days <= 210:
        return "week"
    return "month"


def _bucket_start(local_dt: datetime, bucket: str) -> datetime:
    if bucket == "hour":
        return local_dt.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "week":
        day = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return day - timedelta(days=day.weekday())
    # month
    return local_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _bucket_label(dt: datetime, bucket: str) -> str:
    if bucket == "hour":
        return dt.strftime("%H:00")
    if bucket == "month":
        return dt.strftime("%m.%Y")
    return dt.strftime("%d.%m")


def _iter_buckets(start: datetime, end: datetime, bucket: str):
    """Yield (key, label, start_utc) for every bucket covering [start, end)."""
    cursor = _bucket_start(to_local(start), bucket)
    last = to_local(end - timedelta(microseconds=1))
    while cursor <= last:
        key = cursor.isoformat()
        yield key, _bucket_label(cursor, bucket), cursor.astimezone(timezone.utc)
        if bucket == "hour":
            cursor += timedelta(hours=1)
        elif bucket == "day":
            cursor += timedelta(days=1)
        elif bucket == "week":
            cursor += timedelta(days=7)
        else:
            month = cursor.month + 1
            year = cursor.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            cursor = cursor.replace(year=year, month=month, day=1)


# ─────────────────────────────────────────────────────────────────────────────
# summary
# ─────────────────────────────────────────────────────────────────────────────
async def get_summary(
    db: AsyncSession, start: datetime, end: datetime, date_from: date, date_to: date
) -> PeriodSummary:
    current = await _completed_sessions(db, start, end)
    span = end - start
    previous = await _completed_sessions(db, start - span, start)
    station_count = await _active_station_count(db)

    revenue = _money(sum((s.amount or 0) for s in current))
    sessions = len(current)
    play_seconds = sum(_play_seconds(s) for s in current)
    avg_check = _money(revenue / sessions) if sessions else ZERO

    prev_revenue = _money(sum((s.amount or 0) for s in previous))
    prev_sessions = len(previous)
    prev_play = sum(_play_seconds(s) for s in previous)
    prev_avg = _money(prev_revenue / prev_sessions) if prev_sessions else ZERO

    now = utcnow()
    effective_end = min(end, now)
    period_seconds = max((effective_end - start).total_seconds(), 0)
    capacity = station_count * period_seconds
    utilization = round(play_seconds / capacity * 100, 1) if capacity else 0.0

    return PeriodSummary(
        date_from=date_from,
        date_to=date_to,
        revenue=revenue,
        sessions=sessions,
        transactions=sessions,
        avg_check=avg_check,
        play_seconds=play_seconds,
        utilization=utilization,
        revenue_delta=_delta(float(revenue), float(prev_revenue)),
        sessions_delta=_delta(float(sessions), float(prev_sessions)),
        avg_check_delta=_delta(float(avg_check), float(prev_avg)),
        play_seconds_delta=_delta(float(play_seconds), float(prev_play)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# revenue series
# ─────────────────────────────────────────────────────────────────────────────
async def get_revenue_series(
    db: AsyncSession, start: datetime, end: datetime, bucket: Optional[str]
) -> RevenueSeries:
    bucket = bucket or pick_bucket(start, end)
    sessions = await _completed_sessions(db, start, end)

    keys: list[str] = []
    labels: dict[str, str] = {}
    starts: dict[str, datetime] = {}
    for key, label, start_utc in _iter_buckets(start, end, bucket):
        keys.append(key)
        labels[key] = label
        starts[key] = start_utc

    agg = {key: {"revenue": ZERO, "sessions": 0, "play": 0} for key in keys}
    for s in sessions:
        key = _bucket_start(to_local(s.ended_at), bucket).isoformat()
        if key not in agg:
            continue
        agg[key]["revenue"] += s.amount or 0
        agg[key]["sessions"] += 1
        agg[key]["play"] += _play_seconds(s)

    points = [
        SeriesPoint(
            label=labels[key],
            start=starts[key],
            revenue=_money(agg[key]["revenue"]),
            sessions=agg[key]["sessions"],
            play_seconds=agg[key]["play"],
        )
        for key in keys
    ]
    return RevenueSeries(bucket=bucket, points=points)


# ─────────────────────────────────────────────────────────────────────────────
# breakdowns
# ─────────────────────────────────────────────────────────────────────────────
async def get_station_stats(
    db: AsyncSession, start: datetime, end: datetime
) -> list[StationStat]:
    sessions = await _completed_sessions(db, start, end)
    stations = list(await db.scalars(select(Station).order_by(Station.number)))

    agg: dict[int, dict] = {
        st.id: {"revenue": ZERO, "sessions": 0, "play": 0} for st in stations
    }
    for s in sessions:
        bucket = agg.setdefault(
            s.station_id, {"revenue": ZERO, "sessions": 0, "play": 0}
        )
        bucket["revenue"] += s.amount or 0
        bucket["sessions"] += 1
        bucket["play"] += _play_seconds(s)

    by_id = {st.id: st for st in stations}
    result = [
        StationStat(
            station_id=sid,
            name=by_id[sid].name if sid in by_id else f"PS #{sid}",
            number=by_id[sid].number if sid in by_id else 0,
            revenue=_money(v["revenue"]),
            sessions=v["sessions"],
            play_seconds=v["play"],
        )
        for sid, v in agg.items()
        if v["sessions"] > 0 or sid in by_id
    ]
    result.sort(key=lambda x: (x.revenue, x.sessions), reverse=True)
    return result


async def get_tariff_stats(
    db: AsyncSession, start: datetime, end: datetime
) -> list[TariffStat]:
    sessions = await _completed_sessions(db, start, end)
    agg: dict[Optional[int], dict] = {}
    names: dict[Optional[int], str] = {}
    for s in sessions:
        key = s.tariff_id
        bucket = agg.setdefault(key, {"revenue": ZERO, "sessions": 0})
        bucket["revenue"] += s.amount or 0
        bucket["sessions"] += 1
        names[key] = s.tariff.name if s.tariff else "Без тарифа"

    result = [
        TariffStat(
            tariff_id=tid,
            name=names.get(tid, "Без тарифа"),
            revenue=_money(v["revenue"]),
            sessions=v["sessions"],
        )
        for tid, v in agg.items()
    ]
    result.sort(key=lambda x: (x.revenue, x.sessions), reverse=True)
    return result


async def get_heatmap(
    db: AsyncSession, start: datetime, end: datetime
) -> list[HeatmapCell]:
    sessions = await _completed_sessions(db, start, end)
    grid: dict[tuple[int, int], dict] = {}
    for s in sessions:
        local = to_local(s.ended_at)
        key = (local.weekday(), local.hour)
        bucket = grid.setdefault(key, {"revenue": ZERO, "sessions": 0})
        bucket["revenue"] += s.amount or 0
        bucket["sessions"] += 1
    return [
        HeatmapCell(
            weekday=wd,
            hour=hour,
            revenue=_money(v["revenue"]),
            sessions=v["sessions"],
        )
        for (wd, hour), v in grid.items()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# history / receipts
# ─────────────────────────────────────────────────────────────────────────────
async def get_session_history(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    station_id: Optional[int],
    status: Optional[SessionStatus],
    page: int,
    page_size: int,
) -> SessionHistoryPage:
    filters = [
        Session.started_at >= start,
        Session.started_at < end,
    ]
    if station_id is not None:
        filters.append(Session.station_id == station_id)
    if status is not None:
        filters.append(Session.status == status)

    total = int(
        await db.scalar(select(func.count()).select_from(Session).where(*filters)) or 0
    )
    rows = list(
        await db.scalars(
            select(Session)
            .where(*filters)
            .order_by(Session.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(Session.station), selectinload(Session.tariff))
        )
    )
    items = [_history_item(s) for s in rows]
    return SessionHistoryPage(total=total, page=page, page_size=page_size, items=items)


def _history_item(s: Session) -> SessionHistoryItem:
    return SessionHistoryItem(
        id=s.id,
        station_id=s.station_id,
        station_name=s.station.name if s.station else f"PS #{s.station_id}",
        station_number=s.station.number if s.station else 0,
        tariff_name=s.tariff.name if s.tariff else "Без тарифа",
        type=s.type,
        status=s.status,
        started_at=s.started_at,
        ended_at=s.ended_at,
        duration_minutes=_duration_minutes(s),
        total_paused_seconds=s.total_paused_seconds or 0,
        price_snapshot=s.price_snapshot,
        amount=s.amount,
    )


async def get_receipt(db: AsyncSession, session_id: int) -> Optional[SessionHistoryItem]:
    session = await db.scalar(
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.station), selectinload(Session.tariff))
    )
    return _history_item(session) if session else None


async def get_payments(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    page: int,
    page_size: int,
) -> PaymentPage:
    filters = [Transaction.created_at >= start, Transaction.created_at < end]
    total = int(
        await db.scalar(select(func.count()).select_from(Transaction).where(*filters))
        or 0
    )
    total_amount = _money(
        await db.scalar(select(func.sum(Transaction.amount)).where(*filters))
    )
    rows = list(
        await db.scalars(
            select(Transaction)
            .where(*filters)
            .order_by(Transaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(Transaction.session).selectinload(Session.station))
            .options(selectinload(Transaction.session).selectinload(Session.tariff))
        )
    )
    items = []
    for t in rows:
        sess = t.session
        items.append(
            PaymentItem(
                id=t.id,
                created_at=t.created_at,
                session_id=t.session_id,
                station_name=(
                    sess.station.name
                    if sess and sess.station
                    else f"PS #{sess.station_id if sess else '?'}"
                ),
                tariff_name=(
                    sess.tariff.name if sess and sess.tariff else "Без тарифа"
                ),
                amount=t.amount,
                payment_type=t.payment_type,
            )
        )
    return PaymentPage(
        total=total,
        total_amount=total_amount,
        page=page,
        page_size=page_size,
        items=items,
    )


# ─────────────────────────────────────────────────────────────────────────────
# retention / cleanup
# ─────────────────────────────────────────────────────────────────────────────
async def cleanup_history(
    db: AsyncSession, retention_days: Optional[int] = None
) -> CleanupResult:
    """Delete completed sessions older than the retention window.

    Their transactions are removed first (explicitly, so it works regardless of
    whether the database enforces ON DELETE CASCADE)."""
    days = retention_days if retention_days is not None else settings.HISTORY_RETENTION_DAYS
    cutoff = utcnow() - timedelta(days=days)

    old_sessions = select(Session.id).where(
        Session.status == SessionStatus.COMPLETED,
        Session.ended_at.is_not(None),
        Session.ended_at < cutoff,
    )
    t_result = await db.execute(
        delete(Transaction).where(Transaction.session_id.in_(old_sessions))
    )
    s_result = await db.execute(
        delete(Session).where(
            Session.status == SessionStatus.COMPLETED,
            Session.ended_at.is_not(None),
            Session.ended_at < cutoff,
        )
    )
    await db.commit()
    return CleanupResult(
        deleted_sessions=s_result.rowcount or 0,
        deleted_transactions=t_result.rowcount or 0,
        older_than=cutoff,
        retention_days=days,
    )
