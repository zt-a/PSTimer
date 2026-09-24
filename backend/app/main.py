"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import (
    auth,
    dashboard,
    reports,
    sessions,
    settings as settings_router,
    stations,
    tariffs,
)
from app.telegram.runner import TelegramRunner, set_runner
from app.websocket import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the optional Telegram bot alongside the API."""
    runner = None
    if settings.telegram_enabled:
        runner = TelegramRunner(settings.TELEGRAM_BOT_TOKEN)
        set_runner(runner)
        await runner.start()
    try:
        yield
    finally:
        if runner is not None:
            await runner.stop()
            set_runner(None)


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="PlayStation Club management system MVP",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """Realtime dashboard feed. On connect we push the current snapshot."""
    await manager.connect(websocket)
    try:
        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models import ClubSettings
        from app.services.dashboard import build_dashboard

        async with AsyncSessionLocal() as db:
            settings_row = await db.scalar(
                select(ClubSettings).order_by(ClubSettings.id)
            )
            if settings_row is None:
                db.add(ClubSettings(id=1))
                await db.commit()
            snapshot = await build_dashboard(db)
            await websocket.send_text(
                '{"type":"dashboard","payload":'
                + snapshot.model_dump_json()
                + "}"
            )

        while True:
            # keep the connection alive; ignore client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


app.include_router(auth.router, prefix="/api")
app.include_router(stations.router, prefix="/api")
app.include_router(tariffs.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
