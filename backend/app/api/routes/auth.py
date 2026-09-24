from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models import Admin
from app.schemas import AdminOut, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    admin = await db.scalar(
        select(Admin).where(Admin.username == payload.username)
    )
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin account disabled"
        )

    token = create_access_token(str(admin.id))
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        admin=AdminOut.model_validate(admin),
    )


@router.get("/me", response_model=AdminOut)
async def me(admin: Admin = Depends(get_current_admin)):
    return admin
