"""Reports & analytics endpoints (admin only)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.core.timeutils import local_day_bounds, period_bounds, resolve_range
from app.models import Admin, Session, SessionStatus, Station, Transaction
from app.schemas.schemas import (
    CleanupResult,
    HeatmapCell,
    PaymentPage,
    PeriodSummary,
    RevenueSeries,
    SessionHistoryItem,
    SessionHistoryPage,
    StationStat,
    TariffStat,
)
from app.services import analytics

router = APIRouter(prefix="/reports", tags=["reports"])


def _resolve(
    period: str | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime, datetime, date, date]:
    if period:
        return period_bounds(period)
    return resolve_range(date_from, date_to)


@router.get("/daily")
async def daily_report(
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Backwards-compatible single-day report (local calendar day)."""
    now = datetime.now(timezone.utc)
    day_start, day_end = local_day_bounds(now.date())

    sessions_today = (
        await db.scalars(
            select(Session).where(
                Session.status == SessionStatus.COMPLETED,
                Session.ended_at >= day_start,
                Session.ended_at < day_end,
            )
        )
    ).all()

    total_revenue = sum((s.amount or 0) for s in sessions_today)
    total_play_seconds = 0
    for s in sessions_today:
        if s.ended_at and s.started_at:
            total_play_seconds += max(
                int((s.ended_at - s.started_at).total_seconds())
                - s.total_paused_seconds,
                0,
            )

    stations = {st.id: st.name for st in (await db.scalars(select(Station))).all()}
    transactions = (
        await db.scalars(
            select(Transaction)
            .where(Transaction.created_at >= day_start, Transaction.created_at < day_end)
            .order_by(Transaction.created_at.desc())
            .options(selectinload(Transaction.session).selectinload(Session.tariff))
        )
    ).all()

    lines = []
    for t in transactions:
        sess = t.session
        station_name = stations.get(sess.station_id, f"PS #{sess.station_id}")
        duration_minutes = (
            int((sess.ended_at - sess.started_at).total_seconds() // 60)
            if sess.ended_at and sess.started_at
            else 0
        )
        lines.append(
            {
                "time": t.created_at,
                "station": station_name,
                "session_id": sess.id,
                "duration_minutes": duration_minutes,
                "tariff_name": sess.tariff.name if sess.tariff else "N/A",
                "amount": t.amount,
                "status": sess.status.value,
            }
        )

    return {
        "date": now.date().isoformat(),
        "total_revenue": total_revenue,
        "completed_sessions": len(sessions_today),
        "total_play_seconds": total_play_seconds,
        "num_transactions": len(transactions),
        "lines": lines,
    }


@router.get("/summary", response_model=PeriodSummary)
async def summary(
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    start, end, d_from, d_to = _resolve(period, date_from, date_to)
    return await analytics.get_summary(db, start, end, d_from, d_to)


@router.get("/revenue", response_model=RevenueSeries)
async def revenue_series(
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    bucket: str | None = Query(default=None, pattern="^(hour|day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    start, end, _, _ = _resolve(period, date_from, date_to)
    return await analytics.get_revenue_series(db, start, end, bucket)


@router.get("/stations", response_model=list[StationStat])
async def station_stats(
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    start, end, _, _ = _resolve(period, date_from, date_to)
    return await analytics.get_station_stats(db, start, end)


@router.get("/tariffs", response_model=list[TariffStat])
async def tariff_stats(
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    start, end, _, _ = _resolve(period, date_from, date_to)
    return await analytics.get_tariff_stats(db, start, end)


@router.get("/heatmap", response_model=list[HeatmapCell])
async def heatmap(
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    start, end, _, _ = _resolve(period, date_from, date_to)
    return await analytics.get_heatmap(db, start, end)


@router.get("/sessions", response_model=SessionHistoryPage)
async def session_history(
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    station_id: int | None = Query(default=None),
    status: SessionStatus | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    start, end, _, _ = _resolve(period, date_from, date_to)
    return await analytics.get_session_history(
        db, start, end, station_id, status, page, page_size
    )


@router.get("/sessions/{session_id}", response_model=SessionHistoryItem)
async def session_receipt(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    receipt = await analytics.get_receipt(db, session_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return receipt


@router.get("/payments", response_model=PaymentPage)
async def payments(
    period: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    start, end, _, _ = _resolve(period, date_from, date_to)
    return await analytics.get_payments(db, start, end, page, page_size)


@router.post("/cleanup", response_model=CleanupResult)
async def cleanup(
    retention_days: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Manually purge history older than the retention window."""
    return await analytics.cleanup_history(db, retention_days)
