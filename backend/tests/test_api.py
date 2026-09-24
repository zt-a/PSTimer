from decimal import Decimal
import pytest

from app.core.security import hash_password
from app.models import Admin, Station, StationType, Tariff
from tests.conftest import TestSession


def _admin() -> Admin:
    return Admin(username="admin", password_hash=hash_password("adminpass"), is_active=True)


@pytest.mark.asyncio
async def test_login_flow(client):
    async with TestSession() as db:
        db.add(_admin())
        await db.commit()

    # wrong password -> 401
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401

    # correct login -> token
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["access_token"]
    assert data["admin"]["username"] == "admin"
    return data["access_token"]


@pytest.mark.asyncio
async def test_stations_crud(client, db):
    async with TestSession() as s:
        s.add(_admin())
        await s.commit()
    login = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # unauthenticated -> 401
    assert (await client.get("/api/stations")).status_code == 401

    # create
    r = await client.post(
        "/api/stations",
        json={"name": "PS #1", "number": 1, "type": "PS5", "is_active": True},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    # list
    r = await client.get("/api/stations", headers=headers)
    assert len(r.json()) == 1

    # patch
    r = await client.patch(f"/api/stations/{sid}", json={"is_active": False}, headers=headers)
    assert r.json()["is_active"] is False

    # delete
    assert (await client.delete(f"/api/stations/{sid}", headers=headers)).status_code == 204
    assert (await client.get("/api/stations", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_tariffs_crud(client):
    async with TestSession() as s:
        s.add(_admin())
        await s.commit()
    login = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/tariffs",
        json={"name": "Standard", "price_per_hour": 300, "is_active": True},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    from decimal import Decimal as D
    assert D(str(r.json()["price_per_hour"])) == D("300")

    r = await client.patch(f"/api/tariffs/{tid}", json={"price_per_hour": 400}, headers=headers)
    assert r.json()["price_per_hour"] == "400.00"

    assert (await client.delete(f"/api/tariffs/{tid}", headers=headers)).status_code == 204


@pytest.mark.asyncio
async def test_fixed_session_lifecycle(client):
    async with TestSession() as s:
        s.add(_admin())
        await s.commit()
    login = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    station = await client.post(
        "/api/stations",
        json={"name": "PS #1", "number": 1, "type": "PS5", "is_active": True},
        headers=headers,
    )
    sid = station.json()["id"]

    tariff = await client.post(
        "/api/tariffs",
        json={"name": "Standard", "price_per_hour": 300, "is_active": True},
        headers=headers,
    )
    tid = tariff.json()["id"]

    # start a 60-min session
    r = await client.post(
        "/api/sessions",
        json={"station_id": sid, "tariff_id": tid, "is_open": False, "duration_minutes": 60},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    sess = r.json()
    assert sess["type"] == "FIXED"
    assert sess["status"] == "ACTIVE"

    # two sessions on one station -> 400
    r = await client.post(
        "/api/sessions",
        json={"station_id": sid, "tariff_id": tid, "is_open": False, "duration_minutes": 30},
        headers=headers,
    )
    assert r.status_code == 400

    # pause / resume
    r = await client.post(f"/api/sessions/{sess['id']}/pause", headers=headers)
    assert r.json()["status"] == "PAUSED"
    r = await client.post(f"/api/sessions/{sess['id']}/resume", headers=headers)
    assert r.json()["status"] == "ACTIVE"

    # extend
    r = await client.post(f"/api/sessions/{sess['id']}/extend", json={"duration_minutes": 30}, headers=headers)
    assert r.status_code == 200, r.text

    # stop -> creates transaction, fixed price is 300
    r = await client.post(f"/api/sessions/{sess['id']}/stop", headers=headers)
    assert r.status_code == 200, r.text
    stopped = r.json()
    assert stopped["status"] == "COMPLETED"
    assert Decimal(str(stopped["amount"])) == Decimal("450.00")  # 60+30 min


@pytest.mark.asyncio
async def test_open_session_billing(client):
    from datetime import datetime, timedelta, timezone

    import app.services.session_service as svc
    from app.models import Session, SessionStatus, SessionType

    async with TestSession() as s:
        s.add(_admin())
        await s.commit()
    login = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    station = await client.post(
        "/api/stations",
        json={"name": "PS #1", "number": 1, "type": "PS5", "is_active": True},
        headers=headers,
    )
    sid = station.json()["id"]
    tariff = await client.post(
        "/api/tariffs",
        json={"name": "Open Tariff", "price_per_hour": 300, "is_active": True},
        headers=headers,
    )
    tid = tariff.json()["id"]

    r = await client.post(
        "/api/sessions",
        json={"station_id": sid, "tariff_id": tid, "is_open": True},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    sess = r.json()
    assert sess["type"] == "OPEN"

    # simulate 70 minutes passed without persisting through HTTP (would be slow)
    import asyncio

    async with TestSession() as ss:
        row = await ss.get(Session, sess["id"])
        row.started_at = datetime.now(timezone.utc) - timedelta(minutes=70)
        await ss.commit()

    r = await client.post(f"/api/sessions/{sess['id']}/stop", headers=headers)
    assert r.status_code == 200, r.text
    amount = Decimal(str(r.json()["amount"]))
    # exact per-second billing: 70 min -> 300/60*70 = 350
    assert amount == Decimal("350.00")


@pytest.mark.asyncio
async def test_dashboard_public(client):
    r = await client.get("/api/dashboard")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "stations" in data
    assert "server_time" in data


@pytest.mark.asyncio
async def test_expired_fixed_session_stays_occupied(client):
    """An overdue fixed session must NOT vanish: it stays on the board as
    EXPIRED (station occupied) until the admin stops or extends it."""
    from datetime import datetime, timedelta, timezone

    from app.models import Session

    async with TestSession() as s:
        s.add(_admin())
        await s.commit()
    login = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    station = await client.post(
        "/api/stations",
        json={"name": "PS #1", "number": 1, "type": "PS5", "is_active": True},
        headers=headers,
    )
    sid = station.json()["id"]
    tariff = await client.post(
        "/api/tariffs",
        json={"name": "Standard", "price_per_hour": 300, "is_active": True},
        headers=headers,
    )
    tid = tariff.json()["id"]

    r = await client.post(
        "/api/sessions",
        json={"station_id": sid, "tariff_id": tid, "is_open": False, "duration_minutes": 60},
        headers=headers,
    )
    sess = r.json()

    # push expiry into the past
    async with TestSession() as ss:
        row = await ss.get(Session, sess["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await ss.commit()

    # dashboard still lists the station, now EXPIRED
    dash = (await client.get("/api/dashboard")).json()
    st = next(x for x in dash["stations"] if x["id"] == sid)
    assert st["session_id"] == sess["id"]
    assert st["status"] == "EXPIRED"

    # station is not free: a new session is rejected
    r = await client.post(
        "/api/sessions",
        json={"station_id": sid, "tariff_id": tid, "is_open": False, "duration_minutes": 30},
        headers=headers,
    )
    assert r.status_code == 400

    # admin can extend (revive) ...
    r = await client.post(f"/api/sessions/{sess['id']}/extend", json={"duration_minutes": 30}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ACTIVE"

    # ... and finally settle it
    r = await client.post(f"/api/sessions/{sess['id']}/stop", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_bulk_pause_resume_extend_free(client):
    """Power-outage helpers: pause/resume everything, then add unbilled time to
    FIXED sessions only (OPEN sessions must be ignored and price unchanged)."""
    from datetime import datetime, timedelta, timezone

    from app.models import Session

    async with TestSession() as s:
        s.add(_admin())
        await s.commit()
    login = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "adminpass"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    st1 = (
        await client.post(
            "/api/stations",
            json={"name": "PS #1", "number": 1, "type": "PS5", "is_active": True},
            headers=headers,
        )
    ).json()
    st2 = (
        await client.post(
            "/api/stations",
            json={"name": "PS #2", "number": 2, "type": "PS5", "is_active": True},
            headers=headers,
        )
    ).json()
    tariff = (
        await client.post(
            "/api/tariffs",
            json={"name": "Standard", "price_per_hour": 300, "is_active": True},
            headers=headers,
        )
    ).json()

    fixed = (
        await client.post(
            "/api/sessions",
            json={
                "station_id": st1["id"],
                "tariff_id": tariff["id"],
                "is_open": False,
                "duration_minutes": 60,
            },
            headers=headers,
        )
    ).json()
    opened = (
        await client.post(
            "/api/sessions",
            json={
                "station_id": st2["id"],
                "tariff_id": tariff["id"],
                "is_open": True,
            },
            headers=headers,
        )
    ).json()

    # pause everything (fixed + open)
    r = await client.post("/api/sessions/pause-all", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["affected"] == 2

    # resume everything
    r = await client.post("/api/sessions/resume-all", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["affected"] == 2

    # free extension applies to the fixed session only
    r = await client.post(
        "/api/sessions/extend-all", json={"duration_minutes": 15}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["affected"] == 1

    async with TestSession() as ss:
        row = await ss.get(Session, fixed["id"])
        assert row.comp_seconds == 15 * 60
        open_row = await ss.get(Session, opened["id"])
        assert open_row.comp_seconds == 0

    # price is unchanged despite the extra 15 minutes
    r = await client.post(f"/api/sessions/{fixed['id']}/stop", headers=headers)
    assert Decimal(str(r.json()["amount"])) == Decimal("300.00")


@pytest.mark.asyncio
async def test_extend_all_free_revives_expired(client):
    from datetime import datetime, timedelta, timezone

    from app.models import Session

    async with TestSession() as s:
        s.add(_admin())
        await s.commit()
    login = await client.post(
        "/api/auth/login", json={"username": "admin", "password": "adminpass"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    st = (
        await client.post(
            "/api/stations",
            json={"name": "PS #1", "number": 1, "type": "PS5", "is_active": True},
            headers=headers,
        )
    ).json()
    tariff = (
        await client.post(
            "/api/tariffs",
            json={"name": "Standard", "price_per_hour": 300, "is_active": True},
            headers=headers,
        )
    ).json()
    sess = (
        await client.post(
            "/api/sessions",
            json={
                "station_id": st["id"],
                "tariff_id": tariff["id"],
                "is_open": False,
                "duration_minutes": 60,
            },
            headers=headers,
        )
    ).json()

    async with TestSession() as ss:
        row = await ss.get(Session, sess["id"])
        # started 65 min ago with a 60-min purchase -> already overdue by 5 min
        now = datetime.now(timezone.utc)
        row.started_at = now - timedelta(minutes=65)
        row.expires_at = now - timedelta(minutes=5)
        await ss.commit()

    r = await client.post(
        "/api/sessions/extend-all", json={"duration_minutes": 10}, headers=headers
    )
    assert r.json()["affected"] == 1

    async with TestSession() as ss:
        row = await ss.get(Session, sess["id"])
        assert row.status.value == "ACTIVE"
    r = await client.post(f"/api/sessions/{sess['id']}/stop", headers=headers)
    assert Decimal(str(r.json()["amount"])) == Decimal("300.00")
