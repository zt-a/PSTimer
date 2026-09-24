"""Subscriber storage, station subscriptions and broadcast helpers."""

from __future__ import annotations

import logging

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramStationSubscription, TelegramSubscriber
from app.telegram.client import TelegramClient, TelegramError

logger = logging.getLogger("pstimer.telegram")


async def get(db: AsyncSession, chat_id: int) -> TelegramSubscriber | None:
    return await db.scalar(
        select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id)
    )


async def subscribe(
    db: AsyncSession,
    chat_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> TelegramSubscriber:
    """Create or re-activate a subscriber. New users default to all stations."""
    sub = await get(db, chat_id)
    if sub is None:
        sub = TelegramSubscriber(
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            is_active=True,
            notify_all=True,
        )
        db.add(sub)
    else:
        sub.is_active = True
        sub.username = username
        sub.first_name = first_name
    await db.commit()
    await db.refresh(sub)
    return sub


async def unsubscribe(db: AsyncSession, chat_id: int) -> bool:
    """Fully disable a subscriber (kept for reference, no notifications)."""
    sub = await get(db, chat_id)
    if sub is None:
        return False
    sub.is_active = False
    await db.commit()
    return True


async def deactivate(db: AsyncSession, chat_id: int) -> None:
    sub = await get(db, chat_id)
    if sub is not None and sub.is_active:
        sub.is_active = False
        await db.commit()


async def set_notify_all(db: AsyncSession, chat_id: int, value: bool) -> TelegramSubscriber | None:
    sub = await get(db, chat_id)
    if sub is None:
        return None
    sub.is_active = True
    sub.notify_all = value
    await db.commit()
    await db.refresh(sub)
    return sub


async def clear_stations(db: AsyncSession, chat_id: int) -> None:
    """Remove all per-station subscriptions (notify_all flag is untouched)."""
    sub = await get(db, chat_id)
    if sub is None:
        return
    await db.execute(
        delete(TelegramStationSubscription).where(
            TelegramStationSubscription.subscriber_id == sub.id
        )
    )
    await db.commit()


async def clear_all(db: AsyncSession, chat_id: int) -> None:
    """Turn off every notification for this chat."""
    sub = await get(db, chat_id)
    if sub is None:
        return
    sub.notify_all = False
    await db.execute(
        delete(TelegramStationSubscription).where(
            TelegramStationSubscription.subscriber_id == sub.id
        )
    )
    await db.commit()


async def toggle_station(db: AsyncSession, chat_id: int, station_id: int) -> bool:
    """Toggle a station subscription. Returns the new state (True = subscribed)."""
    sub = await get(db, chat_id)
    if sub is None:
        return False
    existing = await db.scalar(
        select(TelegramStationSubscription).where(
            TelegramStationSubscription.subscriber_id == sub.id,
            TelegramStationSubscription.station_id == station_id,
        )
    )
    if existing is not None:
        await db.delete(existing)
        await db.commit()
        return False
    db.add(
        TelegramStationSubscription(subscriber_id=sub.id, station_id=station_id)
    )
    await db.commit()
    return True


async def subscribed_station_ids(db: AsyncSession, chat_id: int) -> set[int]:
    sub = await get(db, chat_id)
    if sub is None:
        return set()
    rows = await db.scalars(
        select(TelegramStationSubscription.station_id).where(
            TelegramStationSubscription.subscriber_id == sub.id
        )
    )
    return set(rows.all())


async def list_active(db: AsyncSession) -> list[TelegramSubscriber]:
    return list(
        (
            await db.scalars(
                select(TelegramSubscriber).where(TelegramSubscriber.is_active.is_(True))
            )
        ).all()
    )


async def subscribers_for_station(
    db: AsyncSession, station_id: int | None
) -> list[TelegramSubscriber]:
    """Active subscribers interested in ``station_id`` (None = everyone)."""
    stmt = select(TelegramSubscriber).where(TelegramSubscriber.is_active.is_(True))
    if station_id is not None:
        sub_ids = select(TelegramStationSubscription.subscriber_id).where(
            TelegramStationSubscription.station_id == station_id
        )
        stmt = stmt.where(
            or_(TelegramSubscriber.notify_all.is_(True), TelegramSubscriber.id.in_(sub_ids))
        )
    return list((await db.scalars(stmt)).all())


async def broadcast(
    client: TelegramClient,
    db: AsyncSession,
    text: str,
    station_id: int | None = None,
) -> int:
    """Send ``text`` to matching active subscribers. Blocked chats are disabled."""
    sent = 0
    for sub in await subscribers_for_station(db, station_id):
        try:
            await client.send_message(sub.chat_id, text)
            sent += 1
        except TelegramError as exc:
            if exc.is_blocked:
                logger.info("telegram chat %s unreachable, disabling", sub.chat_id)
                await deactivate(db, sub.chat_id)
            else:
                logger.warning("telegram send to %s failed: %s", sub.chat_id, exc)
        except Exception as exc:  # noqa: BLE001 - never break the caller
            logger.warning("telegram send to %s failed: %r", sub.chat_id, exc)
    return sent
