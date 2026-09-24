from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.timeutils import club_tz, local_day_bounds, utcnow
from app.models import (
    Session,
    SessionStatus,
    SessionType,
    Station,
    Tariff,
    Transaction,
)
from app.services import analytics


async def _base(db):
    s1 = Station(name="PS #1", number=1, is_active=True)
    s2 = Station(name="PS #2", number=2, is_active=True)
    tariff = Tariff(name="Std", price_per_hour=Decimal("300"), is_active=True)
    db.add_all([s1, s2, tariff])
    await db.flush()
    return s1, s2, tariff


def _completed(station_id, tariff_id, started, ended, amount, paused=0):
    return Session(
        station_id=station_id,
        tariff_id=tariff_id,
        type=SessionType.OPEN,
        status=SessionStatus.COMPLETED,
        started_at=started,
        ended_at=ended,
        price_snapshot=Decimal("300"),
        amount=Decimal(amount),
        total_paused_seconds=paused,
    )


def _today_bounds():
    today = utcnow().astimezone(club_tz()).date()
    start, end = local_day_bounds(today)
    return today, start, end


@pytest.mark.asyncio
async def test_summary_with_delta(db):
    s1, s2, tariff = await _base(db)
    _, start, end = _today_bounds()
    now = utcnow()

    db.add_all(
        [
            _completed(s1.id, tariff.id, now - timedelta(hours=1), now, 100),
            _completed(s2.id, tariff.id, now - timedelta(hours=2), now, 200),
            # yesterday
            _completed(s1.id, tariff.id, start - timedelta(hours=3), start - timedelta(hours=1), 50),
        ]
    )
    await db.commit()

    summary = await analytics.get_summary(db, start, end, *_dates(start, end))
    assert summary.revenue == Decimal("300.00")
    assert summary.sessions == 2
    assert summary.avg_check == Decimal("150.00")
    assert summary.play_seconds > 0
    # previous day had 50 -> +500%
    assert summary.revenue_delta == 500.0


def _dates(start, end):
    return (start.astimezone(club_tz()).date(), (end - timedelta(seconds=1)).astimezone(club_tz()).date())


@pytest.mark.asyncio
async def test_revenue_series_hourly(db):
    s1, _, tariff = await _base(db)
    _, start, end = _today_bounds()
    # two sessions in the same local hour
    base = start + timedelta(hours=3)
    db.add_all(
        [
            _completed(s1.id, tariff.id, base, base + timedelta(minutes=30), 100),
            _completed(s1.id, tariff.id, base + timedelta(minutes=31), base + timedelta(minutes=50), 50),
        ]
    )
    await db.commit()

    series = await analytics.get_revenue_series(db, start, end, "hour")
    assert series.bucket == "hour"
    assert len(series.points) == 24
    total = sum(p.revenue for p in series.points)
    assert total == Decimal("150.00")
    assert any(p.sessions == 2 for p in series.points)


@pytest.mark.asyncio
async def test_station_and_tariff_breakdown(db):
    s1, s2, tariff = await _base(db)
    _, start, end = _today_bounds()
    now = utcnow()
    db.add_all(
        [
            _completed(s1.id, tariff.id, now - timedelta(hours=1), now, 300),
            _completed(s2.id, tariff.id, now - timedelta(hours=1), now, 100),
        ]
    )
    await db.commit()

    stations = await analytics.get_station_stats(db, start, end)
    assert stations[0].station_id == s1.id
    assert stations[0].revenue == Decimal("300.00")
    by_id = {s.station_id: s for s in stations}
    assert by_id[s2.id].revenue == Decimal("100.00")

    tariffs = await analytics.get_tariff_stats(db, start, end)
    assert tariffs[0].tariff_id == tariff.id
    assert tariffs[0].revenue == Decimal("400.00")
    assert tariffs[0].sessions == 2


@pytest.mark.asyncio
async def test_history_filters_and_pagination(db):
    s1, s2, tariff = await _base(db)
    _, start, end = _today_bounds()
    now = utcnow()
    for i in range(3):
        db.add(_completed(s1.id, tariff.id, now - timedelta(hours=i + 1), now - timedelta(hours=i), 10 * (i + 1)))
    db.add(_completed(s2.id, tariff.id, now - timedelta(hours=1), now, 5))
    await db.commit()

    page = await analytics.get_session_history(db, start, end, None, None, 1, 2)
    assert page.total == 4
    assert len(page.items) == 2
    assert page.items[0].station_name in {"PS #1", "PS #2"}

    filtered = await analytics.get_session_history(db, start, end, s1.id, None, 1, 50)
    assert filtered.total == 3

    receipt = await analytics.get_receipt(db, page.items[0].id)
    assert receipt is not None and receipt.id == page.items[0].id


@pytest.mark.asyncio
async def test_payments(db):
    s1, _, tariff = await _base(db)
    _, start, end = _today_bounds()
    now = utcnow()
    sess = _completed(s1.id, tariff.id, now - timedelta(hours=1), now, 120)
    db.add(sess)
    await db.flush()
    db.add(Transaction(session_id=sess.id, amount=Decimal("120")))
    await db.commit()

    page = await analytics.get_payments(db, start, end, 1, 25)
    assert page.total == 1
    assert page.total_amount == Decimal("120.00")
    assert page.items[0].station_name == "PS #1"
    assert page.items[0].tariff_name == "Std"


@pytest.mark.asyncio
async def test_cleanup_retention(db):
    s1, _, tariff = await _base(db)
    now = utcnow()

    old = _completed(s1.id, tariff.id, now - timedelta(days=40), now - timedelta(days=40) + timedelta(hours=1), 100)
    recent = _completed(s1.id, tariff.id, now - timedelta(days=5), now - timedelta(days=5) + timedelta(hours=1), 200)
    active = Session(
        station_id=s1.id,
        tariff_id=tariff.id,
        type=SessionType.OPEN,
        status=SessionStatus.OPEN,
        started_at=now - timedelta(days=40),
        price_snapshot=Decimal("300"),
    )
    db.add_all([old, recent, active])
    await db.flush()
    db.add_all(
        [
            Transaction(session_id=old.id, amount=Decimal("100")),
            Transaction(session_id=recent.id, amount=Decimal("200")),
        ]
    )
    await db.commit()

    result = await analytics.cleanup_history(db, retention_days=30)
    assert result.deleted_sessions == 1
    assert result.deleted_transactions == 1

    remaining = list(await db.scalars(select(Session)))
    ids = {s.id for s in remaining}
    assert recent.id in ids
    assert active.id in ids  # active session is never purged
    assert old.id not in ids

    remaining_tx = list(await db.scalars(select(Transaction)))
    assert len(remaining_tx) == 1
