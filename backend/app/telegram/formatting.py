"""Message formatting for the Telegram bot (HTML parse mode)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.schemas.schemas import DashboardResponse, StationState


def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def money(amount: object, currency: str) -> str:
    if amount is None or amount == "":
        return "—"
    try:
        n = Decimal(str(amount))
    except Exception:  # noqa: BLE001
        return "—"
    s = f"{n:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} {currency}"


def fmt_hms(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _free(st: StationState) -> bool:
    return st.status is None or not st.session_id


def _remaining(st: StationState, now: datetime) -> Optional[int]:
    if not st.expires_at:
        return None
    exp = _as_aware(st.expires_at)
    if exp is None:
        return None
    return max(0, int((exp - now).total_seconds()))


def _elapsed(st: StationState, now: datetime) -> Optional[int]:
    if not st.started_at:
        return None
    start = _as_aware(st.started_at)
    if start is None:
        return None
    ref = now
    if st.status and st.status.value == "PAUSED" and st.paused_at:
        paused = _as_aware(st.paused_at)
        if paused is not None:
            ref = paused
    return max(0, int((ref - start).total_seconds()) - (st.total_paused_seconds or 0))


def _icon(st: StationState) -> str:
    if _free(st):
        return "⚪"
    status = st.status.value if st.status else ""
    if status == "OPEN":
        return "🟣"
    if status == "PAUSED":
        return "⏸"
    if status == "EXPIRED":
        return "🔴"
    return "🟢"


def _label(st: StationState) -> str:
    if _free(st):
        return "свободно"
    status = st.status.value if st.status else ""
    return {
        "OPEN": "открытая",
        "PAUSED": "пауза",
        "EXPIRED": "время истекло",
        "ACTIVE": "играет",
    }.get(status, status.lower())


def station_line(st: StationState, now: datetime, currency: str) -> str:
    parts = [f"{_icon(st)} <b>{st.name}</b> · {_label(st)}"]
    if not _free(st):
        if st.session_type and st.session_type.value == "OPEN":
            el = _elapsed(st, now)
            if el is not None:
                parts.append(f"⏱ {fmt_hms(el)}")
        else:
            rem = _remaining(st, now)
            if rem is not None:
                parts.append(f"⏳ {fmt_hms(rem)}")
        if st.amount is not None:
            parts.append(money(st.amount, currency))
    return " · ".join(parts)


def stations_message(dashboard: DashboardResponse, now: datetime) -> str:
    stations = dashboard.stations
    busy = sum(1 for s in stations if not _free(s))
    free = len(stations) - busy
    lines = [
        f"🎮 <b>{dashboard.club_name}</b> · станции",
        f"🕐 {now.astimezone().strftime('%H:%M:%S')}",
        "",
    ]
    lines += [station_line(s, now, dashboard.currency) for s in stations]
    lines += ["", f"Итого: занято {busy} · свободно {free}"]
    return "\n".join(lines)


def header(dashboard: DashboardResponse) -> str:
    return f"🎮 <b>{dashboard.club_name}</b>"


def event_start(st: StationState, currency: str, duration_minutes: Optional[int]) -> str:
    if st.session_type and st.session_type.value == "OPEN":
        detail = "открытая (посекундно)"
    else:
        detail = f"{duration_minutes} мин" if duration_minutes else "фикс."
    amount = money(st.amount, currency) if st.amount is not None else "—"
    return (
        f"▶️ <b>{st.name}</b> — старт сессии\n"
        f"Тип: {detail}\n"
        f"Сумма: {amount}"
    )


def event_extend(st: StationState, currency: str, minutes: int) -> str:
    rem = _remaining(st, datetime.now(timezone.utc))
    tail = f"\nОсталось: {fmt_hms(rem)}" if rem is not None else ""
    return f"➕ <b>{st.name}</b> — продлено на {minutes} мин{tail}"


def event_pause(st: StationState) -> str:
    return f"⏸ <b>{st.name}</b> — пауза"


def event_resume(st: StationState) -> str:
    return f"▶️ <b>{st.name}</b> — продолжено"


def event_stop(st: StationState, currency: str) -> str:
    amount = money(st.amount, currency) if st.amount is not None else "—"
    return f"⏹ <b>{st.name}</b> — сессия завершена\nОплата: {amount}"


def event_expired(st: StationState, currency: str) -> str:
    amount = money(st.amount, currency) if st.amount is not None else "—"
    return (
        f"⏰ <b>{st.name}</b> — время истекло\n"
        f"К оплате: {amount}\n"
        f"Клиент ждёт — завершите сессию или продлите."
    )


def event_warning(st: StationState, minutes: int, currency: str) -> str:
    return (
        f"⚠️ <b>{st.name}</b> — осталось {minutes} мин\n"
        f"К оплате: {money(st.amount, currency)}"
    )


def help_message() -> str:
    return (
        "🤖 <b>PS Club бот</b>\n\n"
        "Доступные команды:\n"
        "/stations — состояние всех станций\n"
        "/stop — отключить уведомления\n"
        "/help — эта справка\n\n"
        "Вы подписаны на уведомления: старт, пауза, продление, "
        "предупреждения 5/3/1 мин, истечение времени и завершение сессии."
    )
