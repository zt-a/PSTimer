"""Timezone / date-range helpers for analytics.

All datetimes are stored in UTC. The club operates in a local timezone
(``settings.CLUB_TIMEZONE``), so day/week/month boundaries are computed in
local time and converted back to UTC for querying.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def club_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.CLUB_TIMEZONE)
    except Exception:  # pragma: no cover - invalid tz falls back to UTC
        return ZoneInfo("UTC")


def as_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def to_local(dt: datetime) -> datetime:
    return as_aware(dt).astimezone(club_tz())


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Return [start, end) UTC datetimes covering a local calendar day."""
    tz = club_tz()
    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def resolve_range(
    date_from: date | None, date_to: date | None
) -> tuple[datetime, datetime, date, date]:
    """Resolve an inclusive local date range into a [start, end) UTC range.

    Defaults to today (local) when the dates are omitted.
    """
    today = utcnow().astimezone(club_tz()).date()
    start_day = date_from or today
    end_day = date_to or start_day
    if end_day < start_day:
        start_day, end_day = end_day, start_day
    start_utc, _ = local_day_bounds(start_day)
    _, end_utc = local_day_bounds(end_day)
    return start_utc, end_utc, start_day, end_day


def period_bounds(period: str, now: datetime | None = None) -> tuple[datetime, datetime, date, date]:
    """Return bounds for a named period: today, week, month, year, all."""
    now = now or utcnow()
    local_today = now.astimezone(club_tz()).date()

    if period == "today":
        start_day = local_today
    elif period == "week":
        start_day = local_today - timedelta(days=local_today.weekday())
    elif period == "month":
        start_day = local_today.replace(day=1)
    elif period == "year":
        start_day = local_today.replace(month=1, day=1)
    else:  # "all" or unknown -> retention window
        start_day = local_today - timedelta(days=settings.HISTORY_RETENTION_DAYS)

    start_utc, _ = local_day_bounds(start_day)
    _, end_utc = local_day_bounds(local_today)
    return start_utc, end_utc, start_day, local_today
