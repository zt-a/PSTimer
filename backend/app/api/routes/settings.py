from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models import Admin, ClubSettings
from app.schemas import SettingsOut, SettingsUpdate
from app.websocket import manager

router = APIRouter(prefix="/settings", tags=["settings"])


async def _get_or_create(db: AsyncSession) -> ClubSettings:
    settings = await db.scalar(select(ClubSettings).order_by(ClubSettings.id))
    if settings is None:
        settings = ClubSettings(id=1)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    # Public: the TV dashboard (no auth) needs club name, currency and voice
    # flags. Only PATCH below is admin-protected.
    return await _get_or_create(db)


@router.patch("", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    settings = await _get_or_create(db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(settings, k, v)
    await db.commit()
    await db.refresh(settings)
    try:
        await manager.broadcast({"type": "settings_updated"})
    except Exception:
        pass
    return settings
