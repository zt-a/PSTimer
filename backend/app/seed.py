"""Seed script: creates the initial admin and a default tariff if missing.

Usage:
    python -m app.seed                     # seed if empty
    python -m app.seed --reset-password    # set admin password from ADMIN_PASSWORD
    python -m app.seed --reset-password --username admin
"""

from __future__ import annotations

import asyncio
import sys

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


async def reset_admin_password(username: str | None = None, password: str | None = None) -> None:
    """Set the admin password (from ADMIN_PASSWORD by default).

    Creates the admin if it does not exist yet.
    """
    username = username or settings.ADMIN_USERNAME
    password = password or settings.ADMIN_PASSWORD
    if not password:
        raise SystemExit("No password given: set ADMIN_PASSWORD in the environment.")

    async with AsyncSessionLocal() as db:
        admin = await db.scalar(select(Admin).where(Admin.username == username))
        if admin is None:
            db.add(
                Admin(
                    username=username,
                    password_hash=hash_password(password),
                    is_active=True,
                )
            )
            print(f"Admin '{username}' created with the new password.")
        else:
            admin.password_hash = hash_password(password)
            admin.is_active = True
            print(f"Password for '{username}' updated.")
        await db.commit()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--reset-password" in args:
        def _value(flag: str) -> str | None:
            if flag in args:
                index = args.index(flag)
                if index + 1 < len(args):
                    return args[index + 1]
            return None

        asyncio.run(
            reset_admin_password(
                username=_value("--username"),
                password=_value("--password"),
            )
        )
    else:
        asyncio.run(seed())
