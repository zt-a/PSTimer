from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────
class SessionType(str, Enum):
    FIXED = "FIXED"
    OPEN = "OPEN"


class SessionStatus(str, Enum):
    ACTIVE = "ACTIVE"     # fixed: counting down
    OPEN = "OPEN"         # open: counting up
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"   # fixed: time is up, awaits admin stop
    COMPLETED = "COMPLETED"


class StationType(str, Enum):
    PS4 = "PS4"
    PS5 = "PS5"


class TransactionType(str, Enum):
    SESSION_PAYMENT = "SESSION_PAYMENT"


# ─────────────────────────────────────────────────────────────────────────────
# Mixin
# ─────────────────────────────────────────────────────────────────────────────
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Admin
# ─────────────────────────────────────────────────────────────────────────────
class Admin(Base, TimestampMixin):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ─────────────────────────────────────────────────────────────────────────────
# Station
# ─────────────────────────────────────────────────────────────────────────────
class Station(Base, TimestampMixin):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    type: Mapped[StationType] = mapped_column(
        SAEnum(StationType, name="station_type"), default=StationType.PS5
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list[Session]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tariff
# ─────────────────────────────────────────────────────────────────────────────
class Tariff(Base, TimestampMixin):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    price_per_hour: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list[Session]] = relationship(back_populates="tariff")


# ─────────────────────────────────────────────────────────────────────────────
# Session
# ─────────────────────────────────────────────────────────────────────────────
class Session(Base, TimestampMixin):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_ended_at", "ended_at"),
        Index("ix_sessions_status_ended_at", "status", "ended_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    tariff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tariffs.id", ondelete="SET NULL"), nullable=True
    )

    type: Mapped[SessionType] = mapped_column(
        SAEnum(SessionType, name="session_type")
    )
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, name="session_status"), default=SessionStatus.ACTIVE
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # pause / resume
    paused_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_paused_seconds: Mapped[int] = mapped_column(Integer, default=0)

    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── tariff snapshot (requirement #48/#49: fixed price at purchase) ──
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # per hour

    # billing
    amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )  # fixed final price or open computed price

    # voice duplicate protection (server-side flags, requirement #22)
    warning_5_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_3_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_1_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    expired_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    station: Mapped[Station] = relationship(back_populates="sessions")
    tariff: Mapped[Optional[Tariff]] = relationship(back_populates="sessions")
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Transaction
# ─────────────────────────────────────────────────────────────────────────────
class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, name="transaction_type"),
        default=TransactionType.SESSION_PAYMENT,
    )

    session: Mapped[Session] = relationship(back_populates="transactions")


# ─────────────────────────────────────────────────────────────────────────────
# Club Settings (singleton row, id == 1)
# ─────────────────────────────────────────────────────────────────────────────
class ClubSettings(Base, TimestampMixin):
    __tablename__ = "club_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    club_name: Mapped[str] = mapped_column(String(128), default="PLAYSTATION CLUB")
    currency: Mapped[str] = mapped_column(String(8), default="KGS")
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    warning_5_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    warning_3_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    warning_1_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    expired_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


# ─────────────────────────────────────────────────────────────────────────────
# Telegram subscribers (no auth: anyone who presses /start receives updates)
# ─────────────────────────────────────────────────────────────────────────────
class TelegramSubscriber(Base, TimestampMixin):
    __tablename__ = "telegram_subscribers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
