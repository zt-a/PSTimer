"""Public dashboard for TV + admin (also served over WebSocket)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import ClubSettings
from app.schemas import DashboardResponse
from app.services.dashboard import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
):
    # Ensure settings row exists (singleton)
    settings = await db.scalar(select(ClubSettings).order_by(ClubSettings.id))
    if settings is None:
        settings = ClubSettings(id=1)
        db.add(settings)
        await db.commit()
    return await build_dashboard(db)
