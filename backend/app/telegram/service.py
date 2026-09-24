"""Subscriber storage and broadcast helpers."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramSubscriber
from app.telegram.client import TelegramClient, TelegramError

logger = logging.getLogger("pstimer.telegram")


async def subscribe(
    db: AsyncSession,
    chat_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> TelegramSubscriber:
    sub = await db.scalar(
        select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id)
    )
    if sub is None:
        sub = TelegramSubscriber(
            chat_id=chat_id, username=username, first_name=first_name, is_active=True
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
    sub = await db.scalar(
        select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id)
    )
    if sub is None:
        return False
    sub.is_active = False
    await db.commit()
    return True


async def deactivate(db: AsyncSession, chat_id: int) -> None:
    sub = await db.scalar(
        select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id)
    )
    if sub is not None and sub.is_active:
        sub.is_active = False
        await db.commit()


async def list_active(db: AsyncSession) -> list[TelegramSubscriber]:
    return list(
        (
            await db.scalars(
                select(TelegramSubscriber).where(TelegramSubscriber.is_active.is_(True))
            )
        ).all()
    )


async def broadcast(
    client: TelegramClient, db: AsyncSession, text: str
) -> int:
    """Send ``text`` to every active subscriber. Blocked chats are disabled."""
    sent = 0
    for sub in await list_active(db):
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
