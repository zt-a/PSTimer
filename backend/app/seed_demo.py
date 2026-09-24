"""Populate the database with realistic historical sessions for demos.

Usage::

    python -m app.seed_demo                 # add ~35 days of history
    python -m app.seed_demo --days 60       # longer window
    python -m app.seed_demo --clear         # wipe sessions/transactions first

This is a DEVELOPMENT helper — never run it against a production database.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.timeutils import club_tz, utcnow
from app.models import (
    ClubSettings,
    Session,
    SessionStatus,
    SessionType,
    Station,
    StationType,
    Tariff,
    Transaction,
)

TARIFFS = [
    ("PS5 Standard", Decimal("300")),
    ("PS5 VIP", Decimal("450")),
    ("PS4 Standard", Decimal("200")),
]
FIXED_DURATIONS = [30, 60, 90, 120]
RNG = random.Random(20240924)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _ensure_reference_data(db) -> tuple[list[Station], list[Tariff]]:
    stations = list(await db.scalars(select(Station).order_by(Station.number)))
    if not stations:
        stations = [
            Station(name=f"PS #{i:02d}", number=i, type=StationType.PS5, is_active=i <= 9)
            for i in range(1, 11)
        ]
        db.add_all(stations)

    tariffs = list(await db.scalars(select(Tariff).order_by(Tariff.id)))
    if not tariffs:
        tariffs = [
            Tariff(name=name, price_per_hour=price, is_active=True)
            for name, price in TARIFFS
        ]
        db.add_all(tariffs)

    if await db.get(ClubSettings, 1) is None:
        db.add(ClubSettings(id=1))

    await db.flush()
    return [s for s in stations if s.is_active], tariffs


async def seed(days: int, clear: bool) -> None:
    async with AsyncSessionLocal() as db:
        if clear:
            await db.execute(delete(Transaction))
            await db.execute(delete(Session))
            await db.commit()

        stations, tariffs = await _ensure_reference_data(db)
        tz = club_tz()
        now = utcnow()
        today = now.astimezone(tz).date()
        created = 0

        for offset in range(days):
            day = today - timedelta(days=offset)
            weekend = day.weekday() >= 5
            count = RNG.randint(10, 22) if weekend else RNG.randint(6, 16)

            for _ in range(count):
                station = RNG.choice(stations)
                tariff = RNG.choice(tariffs)
                is_open = RNG.random() < 0.3

                start_hour = RNG.choices(
                    population=[12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
                    weights=[2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 6, 3],
                )[0]
                started_local = datetime.combine(
                    day,
                    time(start_hour, RNG.randint(0, 59), RNG.randint(0, 59)),
                    tzinfo=tz,
                )
                started_at = started_local.astimezone(timezone.utc)

                if is_open:
                    seconds = RNG.randint(15, 180) * 60
                    ended_at = started_at + timedelta(seconds=seconds)
                    amount = _money(tariff.price_per_hour / Decimal(3600) * seconds)
                    session_type = SessionType.OPEN
                else:
                    minutes = RNG.choice(FIXED_DURATIONS)
                    ended_at = started_at + timedelta(minutes=minutes)
                    amount = _money(tariff.price_per_hour / Decimal(60) * minutes)
                    session_type = SessionType.FIXED

                if ended_at > now:
                    continue

                session = Session(
                    station_id=station.id,
                    tariff_id=tariff.id,
                    type=session_type,
                    status=SessionStatus.COMPLETED,
                    started_at=started_at,
                    ended_at=ended_at,
                    price_snapshot=tariff.price_per_hour,
                    amount=amount,
                    total_paused_seconds=0,
                    created_at=ended_at,
                    updated_at=ended_at,
                )
                db.add(session)
                await db.flush()
                db.add(
                    Transaction(
                        session_id=session.id,
                        amount=amount,
                        created_at=ended_at,
                        updated_at=ended_at,
                    )
                )
                created += 1

        await db.commit()
        print(
            f"seeded {created} completed session(s) across {days} day(s) "
            f"({len(stations)} stations, {len(tariffs)} tariffs)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="PSTimer demo data seeder")
    parser.add_argument("--days", type=int, default=35)
    parser.add_argument("--clear", action="store_true", help="delete existing history first")
    args = parser.parse_args()

    import asyncio

    asyncio.run(seed(args.days, args.clear))


if __name__ == "__main__":
    main()
