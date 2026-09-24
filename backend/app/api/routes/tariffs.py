from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.models import Admin, Tariff
from app.schemas import TariffCreate, TariffOut, TariffUpdate

router = APIRouter(prefix="/tariffs", tags=["tariffs"])


@router.get("", response_model=list[TariffOut])
async def list_tariffs(
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    rows = (await db.scalars(select(Tariff).order_by(Tariff.id))).all()
    return rows


@router.post("", response_model=TariffOut, status_code=status.HTTP_201_CREATED)
async def create_tariff(
    payload: TariffCreate,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    tariff = Tariff(**payload.model_dump())
    db.add(tariff)
    try:
        await db.commit()
        await db.refresh(tariff)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Tariff name exists") from exc
    return tariff


@router.patch("/{tariff_id}", response_model=TariffOut)
async def update_tariff(
    tariff_id: int,
    payload: TariffUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    tariff = await db.get(Tariff, tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="Tariff not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tariff, k, v)
    try:
        await db.commit()
        await db.refresh(tariff)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Tariff name exists") from exc
    return tariff


@router.delete("/{tariff_id}", status_code=204)
async def delete_tariff(
    tariff_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
):
    tariff = await db.get(Tariff, tariff_id)
    if tariff is None:
        raise HTTPException(status_code=404, detail="Tariff not found")
    await db.delete(tariff)
    await db.commit()
