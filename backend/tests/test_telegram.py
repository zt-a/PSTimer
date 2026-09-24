from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.schemas.schemas import DashboardResponse, StationState
from app.telegram import formatting as fmt
from app.telegram import service
from app.telegram.client import TelegramError
from app.telegram.runner import TelegramRunner


class FakeClient:
    def __init__(self, blocked=()):
        self.sent: list[tuple[int, str]] = []
        self.blocked = set(blocked)

    async def send_message(self, chat_id: int, text: str):
        if chat_id in self.blocked:
            raise TelegramError("Forbidden: bot was blocked by the user", 403)
        self.sent.append((chat_id, text))
        return {}


@pytest.mark.asyncio
async def test_subscriber_lifecycle(db):
    sub = await service.subscribe(db, 123, username="admin", first_name="A")
    assert sub.is_active
    assert len(await service.list_active(db)) == 1

    # idempotent re-subscribe
    await service.subscribe(db, 123, username="admin2")
    active = await service.list_active(db)
    assert len(active) == 1
    assert active[0].username == "admin2"

    assert await service.unsubscribe(db, 123) is True
    assert await service.list_active(db) == []


@pytest.mark.asyncio
async def test_broadcast_disables_blocked(db):
    await service.subscribe(db, 1)
    await service.subscribe(db, 2)
    client = FakeClient(blocked=[2])
    sent = await service.broadcast(client, db, "hello")
    assert sent == 1
    assert [s.chat_id for s in await service.list_active(db)] == [1]


def _dash(stations, currency="сом"):
    now = datetime.now(timezone.utc)
    return DashboardResponse(
        club_name="PS Club",
        currency=currency,
        voice_enabled=True,
        server_time=now,
        stations=stations,
    )


def _station(session_id, status, **kw):
    base = dict(
        id=1,
        name="PS #01",
        number=1,
        type="PS5",
        is_active=True,
        status=status,
        session_id=session_id,
    )
    base.update(kw)
    return StationState(**base)


def test_stations_message_formatting():
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    dash = DashboardResponse(
        club_name="PS Club",
        currency="сом",
        voice_enabled=True,
        server_time=now,
        stations=[
            _station(None, None),
            _station(
                9,
                "ACTIVE",
                session_type="FIXED",
                started_at=now,
                expires_at=now + timedelta(minutes=30),
                amount=Decimal("150.00"),
            ),
        ],
    )
    msg = fmt.stations_message(dash, now)
    assert "PS #01" in msg
    assert "свободно" in msg
    assert "00:30:00" in msg
    assert "150,00 сом" in msg
    assert "занято 1 · свободно 1" in msg


@pytest.mark.asyncio
async def test_runner_transitions_and_warnings():
    runner = TelegramRunner("test-token")
    sent: list[str] = []

    async def fake_broadcast(text: str) -> None:
        sent.append(text)

    runner._broadcast = fake_broadcast  # type: ignore[assignment]

    now = datetime.now(timezone.utc)

    # baseline: free station
    runner._baseline(_dash([_station(None, None)]))

    # session starts
    await runner._process(
        _dash(
            [
                _station(
                    5,
                    "ACTIVE",
                    session_type="FIXED",
                    started_at=now,
                    expires_at=now + timedelta(minutes=60),
                    amount=Decimal("300.00"),
                )
            ]
        )
    )
    assert any("старт" in s for s in sent)

    # expiry
    sent.clear()
    await runner._process(
        _dash(
            [
                _station(
                    5,
                    "EXPIRED",
                    session_type="FIXED",
                    started_at=now,
                    expires_at=now - timedelta(seconds=1),
                    amount=Decimal("300.00"),
                )
            ]
        )
    )
    assert any("истекло" in s for s in sent)

    # 5-minute warning fires exactly once
    sent.clear()
    soon = now + timedelta(seconds=250)
    await runner._process(
        _dash(
            [
                _station(
                    7,
                    "ACTIVE",
                    session_type="FIXED",
                    started_at=now,
                    expires_at=soon,
                    amount=Decimal("100.00"),
                )
            ]
        )
    )
    assert any("осталось 5 мин" in s for s in sent)
    sent.clear()
    await runner._process(
        _dash(
            [
                _station(
                    7,
                    "ACTIVE",
                    session_type="FIXED",
                    started_at=now,
                    expires_at=soon,
                    amount=Decimal("100.00"),
                )
            ]
        )
    )
    assert sent == []

    # session stops -> completion notification
    sent.clear()
    await runner._process(_dash([_station(None, None)]))
    assert any("завершена" in s for s in sent)
