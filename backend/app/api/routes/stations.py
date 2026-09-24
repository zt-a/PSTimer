from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models import Admin, Station
from app.schemas import StationCreate, StationOut, StationUpdate

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=list[StationOut])
async def list_stations(
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    rows = (await db.scalars(select(Station).order_by(Station.number))).all()
    return rows


@router.post("", response_model=StationOut, status_code=status.HTTP_201_CREATED)
async def create_station(
    payload: StationCreate,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    station = Station(**payload.model_dump())
    db.add(station)
    try:
        await db.commit()
        await db.refresh(station)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Station name or number exists") from exc
    return station


@router.patch("/{station_id}", response_model=StationOut)
async def update_station(
    station_id: int,
    payload: StationUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    station = await db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(station, k, v)
    try:
        await db.commit()
        await db.refresh(station)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Station name or number exists") from exc
    return station


@router.delete("/{station_id}", status_code=204)
async def delete_station(
    station_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    station = await db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    await db.delete(station)
    await db.commit()
