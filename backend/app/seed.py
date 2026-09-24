"""Seed script: creates the initial admin and a default tariff if missing.

Usage: python -m app.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.models import Admin, ClubSettings, Tariff


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        admin = await db.scalar(select(Admin).limit(1))
        if admin is None:
            db.add(
                Admin(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    is_active=True,
                )
            )
            print(f"Admin '{settings.ADMIN_USERNAME}' created.")

        tariff = await db.scalar(select(Tariff).limit(1))
        if tariff is None:
            db.add(
                Tariff(
                    name="PS5 Standard",
                    price_per_hour="300",
                )
            )
            print("Default tariff 'PS5 Standard' (300/hour) created.")

        club_settings = await db.scalar(select(ClubSettings).limit(1))
        if club_settings is None:
            db.add(ClubSettings(id=1))
            print("Club settings initialized.")

        # default 9 stations (not hardcoded for the app - just initial seeding)
        from app.models import Station, StationType

        existing = await db.scalar(select(Station).limit(1))
        if existing is None:
            for number in range(1, 10):
                db.add(
                    Station(
                        name=f"PS #{number:02d}",
                        number=number,
                        type=StationType.PS5,
                        is_active=True,
                    )
                )
            db.add(Station(name="PS #10", number=10, type=StationType.PS5, is_active=False))
            print("9 default stations created (1 extra disabled).")

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
