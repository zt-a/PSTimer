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
    assert sub.notify_all is True  # new users get all stations by default
    assert len(await service.list_active(db)) == 1

    # idempotent re-subscribe
    await service.subscribe(db, 123, username="admin2")
    active = await service.list_active(db)
    assert len(active) == 1
    assert active[0].username == "admin2"

    assert await service.unsubscribe(db, 123) is True
    assert await service.list_active(db) == []


@pytest.mark.asyncio
async def test_station_subscriptions(db):
    await service.subscribe(db, 10)
    # explicit station selection turns "all" off
    await service.set_notify_all(db, 10, False)
    assert await service.toggle_station(db, 10, 1) is True
    assert await service.toggle_station(db, 10, 2) is True
    assert await service.subscribed_station_ids(db, 10) == {1, 2}

    # toggle removes
    assert await service.toggle_station(db, 10, 1) is False
    assert await service.subscribed_station_ids(db, 10) == {2}

    # clear_all disables everything
    await service.clear_all(db, 10)
    assert await service.subscribed_station_ids(db, 10) == set()
    sub = await service.get(db, 10)
    assert sub.notify_all is False


@pytest.mark.asyncio
async def test_subscribers_for_station_scoping(db):
    all_sub = await service.subscribe(db, 1)  # notify_all=True
    await service.subscribe(db, 2)
    await service.set_notify_all(db, 2, False)
    await service.toggle_station(db, 2, 5)  # only station 5

    station_5 = {s.chat_id for s in await service.subscribers_for_station(db, 5)}
    station_9 = {s.chat_id for s in await service.subscribers_for_station(db, 9)}
    assert station_5 == {1, 2}
    assert station_9 == {1}
    assert all_sub.chat_id == 1


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


def test_stations_keyboard_reflects_subscriptions():
    stations = [_station(None, None), _station(None, None)]
    stations[0].id = 1
    stations[0].name = "PS #01"
    stations[1].id = 2
    stations[1].name = "PS #02"

    kb = fmt.stations_keyboard(stations, notify_all=False, subscribed_ids={1})
    buttons = {b["callback_data"]: b["text"] for row in kb["inline_keyboard"] for b in row}
    assert buttons["tog:1"].startswith("✅")
    assert buttons["tog:2"].startswith("➕")
    assert buttons["all:on"].startswith("⬜")

    kb_all = fmt.stations_keyboard(stations, notify_all=True, subscribed_ids=set())
    buttons_all = {
        b["callback_data"]: b["text"] for row in kb_all["inline_keyboard"] for b in row
    }
    assert buttons_all["tog:1"].startswith("✅")
    assert buttons_all["all:off"].startswith("✅")


@pytest.mark.asyncio
async def test_runner_transitions_and_warnings():
    runner = TelegramRunner("test-token")
    sent: list[str] = []

    async def fake_broadcast(text: str, station_id=None) -> None:
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


def test_bulk_event_messages():
    assert "паузу" in fmt.event_pause_all(3)
    assert "3" in fmt.event_pause_all(3)
    assert "возобновлены" in fmt.event_resume_all(2)
    assert "2" in fmt.event_resume_all(2)
    assert "15" in fmt.event_extend_all(4, 15)
    assert "4" in fmt.event_extend_all(4, 15)


@pytest.mark.asyncio
async def test_notify_bulk_broadcasts_to_all_and_resyncs():
    runner = TelegramRunner("test-token")
    sent: list[tuple[str, object]] = []

    async def fake_broadcast(text: str, station_id=None) -> None:
        sent.append((text, station_id))

    snapshot = _dash(
        [
            _station(
                5,
                "PAUSED",
                session_type="FIXED",
                started_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
        ]
    )

    async def fake_snapshot():
        return snapshot

    runner.broadcast = fake_broadcast  # type: ignore[assignment]
    runner._snapshot = fake_snapshot  # type: ignore[assignment]

    await runner.notify_bulk("все на паузе")
    assert sent == [("все на паузе", None)]
    # baseline resynced so the monitor won't re-send a per-station notice
    assert runner._prev[1].status.value == "PAUSED"
