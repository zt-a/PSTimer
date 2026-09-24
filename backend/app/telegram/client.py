"""Minimal async Telegram Bot API client built on httpx.

Only the handful of methods we need are implemented, so there is no heavy
dependency on python-telegram-bot.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger("pstimer.telegram")

API_BASE = "https://api.telegram.org"


class TelegramError(Exception):
    """Raised when the Bot API answers with ok=false."""

    def __init__(self, description: str, error_code: Optional[int] = None) -> None:
        super().__init__(description)
        self.description = description
        self.error_code = error_code

    @property
    def is_blocked(self) -> bool:
        """True when the chat can no longer receive messages (blocked/kicked)."""
        d = self.description.lower()
        return (
            self.error_code == 403
            or "blocked" in d
            or "chat not found" in d
            or "user is deactivated" in d
            or "kicked" in d
        )


class TelegramClient:
    def __init__(self, token: str) -> None:
        self._token = token.strip()
        self._client: Optional[httpx.AsyncClient] = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"{API_BASE}/bot{self._token}",
                timeout=httpx.Timeout(40.0, connect=10.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _call(self, method: str, **params: Any) -> Any:
        client = await self._http()
        try:
            res = await client.post(f"/{method}", json=params)
        except httpx.HTTPError as exc:
            raise TelegramError(f"network error: {exc}") from exc

        try:
            data = res.json()
        except ValueError as exc:
            raise TelegramError(f"invalid response ({res.status_code})") from exc

        if not data.get("ok"):
            raise TelegramError(
                data.get("description", "unknown error"),
                data.get("error_code"),
            )
        return data.get("result")

    async def get_me(self) -> dict:
        return await self._call("getMe")

    async def get_updates(
        self, offset: Optional[int], timeout: int = 25
    ) -> list[dict]:
        params: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            params["offset"] = offset
        return await self._call("getUpdates", **params)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
        reply_markup: Optional[dict] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
            "disable_notification": disable_notification,
        }
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return await self._call("sendMessage", **params)

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[dict] = None,
    ) -> Any:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return await self._call("editMessageText", **params)

    async def answer_callback_query(
        self, callback_query_id: str, text: Optional[str] = None
    ) -> Any:
        params: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            params["text"] = text
        return await self._call("answerCallbackQuery", **params)
