"""Telegram bot runner: command/keyboard handling + event notifications.

Two concurrent tasks:
  * long-poll ``getUpdates`` to handle commands and inline-keyboard buttons
    (subscription menu: all stations or a chosen subset);
  * a monitor that periodically snapshots the dashboard and turns state
    transitions into notifications (start, pause, resume, extend, 5/3/1-min
    warnings, expiry, completion), delivered only to subscribers of the
    relevant station.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.schemas.schemas import DashboardResponse, StationState
from app.services.dashboard import build_dashboard
from app.telegram import formatting as fmt
from app.telegram import service
from app.telegram.client import TelegramClient, TelegramError

logger = logging.getLogger("pstimer.telegram")

WARNING_THRESHOLDS = (300, 180, 60)  # seconds -> 5/3/1 minutes


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class TelegramRunner:
    def __init__(self, token: str) -> None:
        self.client = TelegramClient(token)
        self._poll_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()
        self._prev: dict[int, StationState] = {}
        self._warned: dict[int, set[int]] = {}
        self._last_rem: dict[int, int] = {}

    # ── lifecycle ────────────────────────────────────────────────────────
    async def start(self) -> None:
        try:
            me = await self.client.get_me()
            logger.info("telegram bot @%s started", me.get("username"))
        except TelegramError as exc:
            logger.error("telegram bot token invalid: %s", exc)
            return
        self._poll_task = asyncio.create_task(self._poll_updates())
        self._monitor_task = asyncio.create_task(self._monitor_events())

    async def stop(self) -> None:
        self._stopping.set()
        for task in (self._poll_task, self._monitor_task):
            if task is not None:
                task.cancel()
        for task in (self._poll_task, self._monitor_task):
            if task is not None:
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
        await self.client.aclose()

    # ── snapshots ────────────────────────────────────────────────────────
    async def _snapshot(self) -> DashboardResponse:
        async with AsyncSessionLocal() as db:
            snapshot = await build_dashboard(db)
            # persist any FIXED -> EXPIRED flips made by build_dashboard
            await db.commit()
            return snapshot

    # ── command polling ──────────────────────────────────────────────────
    async def _poll_updates(self) -> None:
        offset: Optional[int] = None
        while not self._stopping.is_set():
            try:
                updates = await self.client.get_updates(
                    offset, timeout=settings.TELEGRAM_UPDATE_TIMEOUT
                )
            except TelegramError as exc:
                logger.warning("getUpdates failed: %s", exc)
                await asyncio.sleep(5)
                continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("getUpdates error: %r", exc)
                await asyncio.sleep(5)
                continue

            for update in updates:
                offset = update.get("update_id", 0) + 1
                try:
                    await self._handle_update(update)
                except Exception:  # noqa: BLE001
                    logger.exception("failed to handle update %s", update.get("update_id"))

    async def _handle_update(self, update: dict) -> None:
        if update.get("callback_query"):
            await self._handle_callback(update["callback_query"])
            return
        message = update.get("message")
        if not message:
            return
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return
        sender = message.get("from") or {}
        text = (message.get("text") or "").strip()

        if not text.startswith("/"):
            if text:
                await self._show_main(chat_id, None)
            return

        command = text.split()[0].split("@")[0].lower()

        if command == "/start":
            async with AsyncSessionLocal() as db:
                await service.subscribe(
                    db,
                    chat_id,
                    username=sender.get("username"),
                    first_name=sender.get("first_name"),
                )
            await self._show_main(chat_id, None)
        elif command == "/stop":
            async with AsyncSessionLocal() as db:
                await service.clear_all(db, chat_id)
            await self._safe_send(
                chat_id, fmt.stop_message(), fmt.main_menu_keyboard()
            )
        elif command in ("/stations", "/status"):
            await self._show_stations(chat_id, None)
        elif command in ("/subs", "/subscriptions"):
            await self._show_subs(chat_id, None)
        elif command == "/menu":
            await self._show_main(chat_id, None)
        else:
            await self._safe_send(
                chat_id, fmt.help_message(), fmt.main_menu_keyboard()
            )

    # ── callback buttons ─────────────────────────────────────────────────
    async def _handle_callback(self, cq: dict) -> None:
        data = cq.get("data") or ""
        message = cq.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        sender = cq.get("from") or {}
        if chat_id is None:
            return

        try:
            await self.client.answer_callback_query(cq.get("id"))
        except TelegramError:
            pass

        async with AsyncSessionLocal() as db:
            if await service.get(db, chat_id) is None:
                await service.subscribe(
                    db,
                    chat_id,
                    username=sender.get("username"),
                    first_name=sender.get("first_name"),
                )

        if data == "menu:main":
            await self._show_main(chat_id, message_id)
        elif data == "menu:stations":
            await self._show_stations(chat_id, message_id)
        elif data == "menu:subs":
            await self._show_subs(chat_id, message_id)
        elif data == "menu:help":
            await self._edit(
                chat_id, message_id, fmt.help_message(), fmt.back_keyboard()
            )
        elif data.startswith("tog:"):
            try:
                station_id = int(data[4:])
            except ValueError:
                return
            await self._toggle_station(chat_id, station_id)
            await self._show_stations(chat_id, message_id)
        elif data == "all:on":
            async with AsyncSessionLocal() as db:
                await service.set_notify_all(db, chat_id, True)
                await service.clear_stations(db, chat_id)
            await self._show_stations(chat_id, message_id)
        elif data == "all:off":
            async with AsyncSessionLocal() as db:
                await service.clear_all(db, chat_id)
            await self._show_subs(chat_id, message_id)

    async def _toggle_station(self, chat_id: int, station_id: int) -> None:
        """Toggle one station. If 'all' was on, switch to a custom selection
        that includes every station except the tapped one (i.e. mute it)."""
        snapshot = await self._snapshot()
        async with AsyncSessionLocal() as db:
            sub = await service.get(db, chat_id)
            if sub is None:
                return
            if sub.notify_all:
                await service.set_notify_all(db, chat_id, False)
                await service.clear_stations(db, chat_id)
                for st in snapshot.stations:
                    if st.id != station_id:
                        await service.toggle_station(db, chat_id, st.id)
            else:
                await service.toggle_station(db, chat_id, station_id)

    async def _show_main(self, chat_id: int, message_id: Optional[int]) -> None:
        async with AsyncSessionLocal() as db:
            sub = await service.get(db, chat_id)
        text = f"{fmt.menu_message()}\n\n{fmt.subscriptions_text(sub)}"
        await self._edit(chat_id, message_id, text, fmt.main_menu_keyboard())

    async def _show_subs(self, chat_id: int, message_id: Optional[int]) -> None:
        async with AsyncSessionLocal() as db:
            sub = await service.get(db, chat_id)
        text = fmt.subscriptions_text(sub)
        await self._edit(chat_id, message_id, text, fmt.subs_keyboard())

    async def _show_stations(self, chat_id: int, message_id: Optional[int]) -> None:
        snapshot = await self._snapshot()
        async with AsyncSessionLocal() as db:
            sub = await service.get(db, chat_id)
            notify_all = bool(sub and sub.notify_all)
            ids = await service.subscribed_station_ids(db, chat_id)
        text = fmt.stations_message(snapshot, datetime.now(timezone.utc))
        keyboard = fmt.stations_keyboard(snapshot.stations, notify_all, ids)
        await self._edit(chat_id, message_id, text, keyboard)

    async def _edit(
        self,
        chat_id: int,
        message_id: Optional[int],
        text: str,
        keyboard: Optional[dict],
    ) -> None:
        if message_id is None:
            await self._safe_send(chat_id, text, keyboard)
            return
        try:
            await self.client.edit_message_text(
                chat_id, message_id, text, reply_markup=keyboard
            )
        except TelegramError as exc:
            if "not modified" in exc.description.lower():
                return
            await self._safe_send(chat_id, text, keyboard)

    async def _safe_send(
        self, chat_id: int, text: str, keyboard: Optional[dict] = None
    ) -> None:
        try:
            await self.client.send_message(chat_id, text, reply_markup=keyboard)
        except TelegramError as exc:
            if exc.is_blocked:
                async with AsyncSessionLocal() as db:
                    await service.deactivate(db, chat_id)
            else:
                logger.warning("send to %s failed: %s", chat_id, exc)

    async def broadcast(self, text: str, station_id: Optional[int] = None) -> None:
        """Send a message to matching active subscribers (None = everyone)."""
        async with AsyncSessionLocal() as db:
            await service.broadcast(self.client, db, text, station_id=station_id)

    async def _broadcast(self, text: str, station_id: Optional[int] = None) -> None:
        await self.broadcast(text, station_id)

    async def notify_bulk(self, text: str) -> None:
        """Broadcast a global (all-stations) event and resync the monitor
        baseline so per-station transition notices aren't duplicated."""
        await self.broadcast(text)
        try:
            snapshot = await self._snapshot()
            self._baseline(snapshot)
        except Exception:  # noqa: BLE001
            logger.exception("telegram bulk resync failed")

    # ── event monitor ────────────────────────────────────────────────────
    async def _monitor_events(self) -> None:
        interval = max(settings.TELEGRAM_POLL_INTERVAL, 5)
        logger.info("telegram event monitor started (every %ss)", interval)
        # baseline first pass: record state without notifying
        try:
            snapshot = await self._snapshot()
            self._baseline(snapshot)
        except Exception:  # noqa: BLE001
            logger.exception("telegram baseline failed")

        while not self._stopping.is_set():
            await asyncio.sleep(interval)
            try:
                snapshot = await self._snapshot()
                await self._process(snapshot)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("telegram monitor cycle failed")

    def _baseline(self, dashboard: DashboardResponse) -> None:
        for st in dashboard.stations:
            self._prev[st.id] = st

    async def _process(self, dashboard: DashboardResponse) -> None:
        now = datetime.now(timezone.utc)
        currency = dashboard.currency
        seen: set[int] = set()
        for st in dashboard.stations:
            seen.add(st.id)
            prev = self._prev.get(st.id)
            if prev is not None:
                await self._transition(prev, st, currency)
            self._prev[st.id] = st
            await self._check_warnings(st, currency)
        for sid in list(self._prev):
            if sid not in seen:
                del self._prev[sid]

    async def _transition(
        self, prev: StationState, cur: StationState, currency: str
    ) -> None:
        p_sid, c_sid = prev.session_id, cur.session_id

        if p_sid != c_sid:
            if c_sid and not p_sid:
                await self._broadcast(
                    fmt.event_start(cur, currency, self._purchased_minutes(cur)),
                    cur.id,
                )
            elif p_sid and not c_sid:
                await self._broadcast(fmt.event_stop(prev, currency), prev.id)
            else:  # occupied by a different session
                await self._broadcast(fmt.event_stop(prev, currency), prev.id)
                await self._broadcast(
                    fmt.event_start(cur, currency, self._purchased_minutes(cur)),
                    cur.id,
                )
            return

        ps = prev.status.value if prev.status else None
        cs = cur.status.value if cur.status else None
        if ps == cs:
            return

        if cs == "EXPIRED":
            await self._broadcast(fmt.event_expired(cur, currency), cur.id)
        elif cs == "PAUSED":
            await self._broadcast(fmt.event_pause(cur), cur.id)
        elif cs == "ACTIVE" and ps in ("PAUSED", "EXPIRED"):
            # resume or post-extend revival -> re-arm warnings
            self._warned.pop(c_sid or -1, None)
            self._last_rem.pop(c_sid or -1, None)
            await self._broadcast(fmt.event_resume(cur), cur.id)

    async def _check_warnings(self, st: StationState, currency: str) -> None:
        if (
            st.session_id is None
            or st.session_type is None
            or st.session_type.value != "FIXED"
            or st.status is None
            or st.status.value != "ACTIVE"
            or not st.expires_at
        ):
            return
        exp = _aware(st.expires_at)
        if exp is None:
            return
        rem = max(0, int((exp - datetime.now(timezone.utc)).total_seconds()))

        last = self._last_rem.get(st.session_id)
        if last is not None and rem > last + 30:
            # time was extended -> warnings should fire again
            self._warned.pop(st.session_id, None)
        self._last_rem[st.session_id] = rem

        if rem > WARNING_THRESHOLDS[0]:
            return
        bucket = 1 if rem <= 60 else 3 if rem <= 180 else 5
        warned = self._warned.setdefault(st.session_id, set())
        if bucket in warned:
            return
        warned.add(bucket)
        await self._broadcast(fmt.event_warning(st, bucket, currency), st.id)

    @staticmethod
    def _purchased_minutes(st: StationState) -> Optional[int]:
        if st.session_type is None or st.session_type.value != "FIXED":
            return None
        start, exp = _aware(st.started_at), _aware(st.expires_at)
        if start is None or exp is None:
            return None
        total = (exp - start).total_seconds() - (st.total_paused_seconds or 0)
        return max(0, round(total / 60))


_runner: Optional[TelegramRunner] = None


def get_runner() -> Optional[TelegramRunner]:
    return _runner


def set_runner(runner: Optional[TelegramRunner]) -> None:
    global _runner
    _runner = runner


async def run_forever() -> None:
    """Standalone entrypoint: python -m app.telegram.runner"""
    runner = TelegramRunner(settings.TELEGRAM_BOT_TOKEN)
    set_runner(runner)
    await runner.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await runner.stop()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not settings.telegram_enabled:
        logger.error("TELEGRAM_BOT_TOKEN is not set — nothing to run")
        return
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
