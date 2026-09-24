"""Session endpoints. Every successful mutation broadcasts the fresh dashboard
snapshot to all connected /ws/dashboard clients."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models import Admin, Session, Tariff
from app.schemas import BulkResult, SessionExtend, SessionOut, SessionStart
from app.services import session_service
from app.services.dashboard import build_dashboard
from app.telegram import formatting as tg_format
from app.telegram.runner import get_runner
from app.websocket import manager

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _notify_telegram(text: str) -> None:
    """Best-effort global Telegram notification for bulk actions."""
    runner = get_runner()
    if runner is None:
        return
    try:
        await runner.notify_bulk(text)
    except Exception as exc:  # noqa: BLE001 - never break the API response
        import logging

        logging.getLogger(__name__).warning("telegram bulk notify failed: %r", exc)


async def _ensure_session(db: AsyncSession, session_id: int) -> Session:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/active", response_model=list[SessionOut])
async def list_active_session(
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):

    sessions = await session_service.list_active(db)
    return [
        SessionOut(
            **{
                **{
                    c: getattr(s, c)
                    for c in SessionOut.model_fields
                    if hasattr(s, c)
                },
            }
        )
        for s in sessions
    ]


@router.post("/pause-all", response_model=BulkResult)
async def pause_all_sessions(
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Power-outage helper: pause every running session."""
    affected = await session_service.pause_all_sessions(db)
    await db.commit()
    await _broadcast(db)
    if affected:
        await _notify_telegram(tg_format.event_pause_all(len(affected)))
    return BulkResult(affected=len(affected))


@router.post("/resume-all", response_model=BulkResult)
async def resume_all_sessions(
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Resume every paused session."""
    affected = await session_service.resume_all_sessions(db)
    await db.commit()
    await _broadcast(db)
    if affected:
        await _notify_telegram(tg_format.event_resume_all(len(affected)))
    return BulkResult(affected=len(affected))


@router.post("/extend-all", response_model=BulkResult)
async def extend_all_sessions(
    payload: SessionExtend,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Add free (unbilled) minutes to every active FIXED session.

    OPEN sessions are ignored and the price is never changed."""
    try:
        affected = await session_service.extend_all_free(db, payload.duration_minutes)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(db)
    if affected:
        await _notify_telegram(
            tg_format.event_extend_all(len(affected), payload.duration_minutes)
        )
    return BulkResult(affected=len(affected))


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def start_session(
    payload: SessionStart,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    tariff = await db.get(Tariff, payload.tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="Tariff not found")
    if not tariff.is_active:
        raise HTTPException(status_code=400, detail="Tariff is inactive")

    try:
        session = await session_service.create_session(
            db,
            station_id=payload.station_id,
            tariff=tariff,
            is_open=payload.is_open,
            duration_minutes=payload.duration_minutes,
        )
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await db.commit()
    session = await _ensure_session(db, session.id)
    await _broadcast(db)
    return SessionOut.model_validate(session)


@router.post("/{session_id}/extend", response_model=SessionOut)
async def extend_session(
    session_id: int,
    payload: SessionExtend,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    session = await _ensure_session(db, session_id)
    try:
        session = await session_service.extend_session(db, session, payload.duration_minutes)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(db)
    return SessionOut.model_validate(session)


@router.post("/{session_id}/pause", response_model=SessionOut)
async def pause_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    session = await _ensure_session(db, session_id)
    try:
        session = await session_service.pause_session(db, session)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(db)
    return SessionOut.model_validate(session)


@router.post("/{session_id}/resume", response_model=SessionOut)
async def resume_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    session = await _ensure_session(db, session_id)
    try:
        session = await session_service.resume_session(db, session)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(db)
    return SessionOut.model_validate(session)


@router.post("/{session_id}/stop", response_model=SessionOut)
async def stop_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    session = await _ensure_session(db, session_id)
    try:
        session, amount = await session_service.stop_session(db, session)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _broadcast(db)
    return SessionOut.model_validate(session)




@router.post("/{session_id}/warnings", response_model=SessionOut)
async def mark_warnings(
    session_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    """Server-side dedup record that a voice warning was already spoken."""
    session = await _ensure_session(db, session_id)
    flags = {
        "warning_5_sent": payload.get("warning_5_sent"),
        "warning_3_sent": payload.get("warning_3_sent"),
        "warning_1_sent": payload.get("warning_1_sent"),
        "expired_sent": payload.get("expired_sent"),
    }
    for k, v in flags.items():
        if v is not None:
            setattr(session, k, bool(v))
    await db.commit()
    await _broadcast(db)
    return SessionOut.model_validate(session)


async def _broadcast(db: AsyncSession) -> None:
    """Best effort push of the latest dashboard snapshot to all WS clients."""
    try:
        snapshot = await build_dashboard(db)
        await manager.broadcast(
            {"type": "dashboard", "payload": snapshot.model_dump(mode="json")}
        )
    except Exception as exc:  # noqa: BLE001
        # Broadcasting must never break the API response.
        import logging

        logging.getLogger(__name__).warning("broadcast failed: %r", exc)
