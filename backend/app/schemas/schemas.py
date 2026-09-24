from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import (
    SessionStatus,
    SessionType,
    StationType,
    TransactionType,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class AdminOut(ORMModel):
    id: int
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    admin: AdminOut


# ─────────────────────────────────────────────────────────────────────────────
# Stations
# ─────────────────────────────────────────────────────────────────────────────
class StationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    number: int = Field(ge=1)
    type: StationType = StationType.PS5
    is_active: bool = True


class StationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=32)
    number: Optional[int] = Field(default=None, ge=1)
    type: Optional[StationType] = None
    is_active: Optional[bool] = None


class StationOut(ORMModel):
    id: int
    name: str
    number: int
    type: StationType
    is_active: bool


# ─────────────────────────────────────────────────────────────────────────────
# Tariffs
# ─────────────────────────────────────────────────────────────────────────────
class TariffCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    price_per_hour: Decimal = Field(gt=0)
    is_active: bool = True


class TariffUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    price_per_hour: Optional[Decimal] = Field(default=None, gt=0)
    is_active: Optional[bool] = None


class TariffOut(ORMModel):
    id: int
    name: str
    price_per_hour: Decimal
    is_active: bool


# ─────────────────────────────────────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────────────────────────────────────
class SessionStart(BaseModel):
    station_id: int
    tariff_id: int
    is_open: bool = False
    duration_minutes: Optional[int] = Field(default=None, ge=1)


class SessionExtend(BaseModel):
    duration_minutes: int = Field(ge=1)


class SessionOut(ORMModel):
    id: int
    station_id: int
    tariff_id: Optional[int] = None
    type: SessionType
    status: SessionStatus
    started_at: datetime
    expires_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    total_paused_seconds: int = 0
    price_snapshot: Decimal
    amount: Optional[Decimal] = None
    warning_5_sent: bool = False
    warning_3_sent: bool = False
    warning_1_sent: bool = False
    expired_sent: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard / TV
# ─────────────────────────────────────────────────────────────────────────────
class StationState(BaseModel):
    id: int
    name: str
    number: int
    type: StationType
    is_active: bool
    status: Optional[SessionStatus] = None          # None == FREE
    session_id: Optional[int] = None
    session_type: Optional[SessionType] = None
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    total_paused_seconds: int = 0
    price_snapshot: Optional[Decimal] = None
    amount: Optional[Decimal] = None                # live computed for open/fixed
    warning_5_sent: bool = False
    warning_3_sent: bool = False
    warning_1_sent: bool = False
    expired_sent: bool = False


class DashboardResponse(BaseModel):
    club_name: str
    currency: str
    voice_enabled: bool
    server_time: datetime
    stations: list[StationState]


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────
class SettingsUpdate(BaseModel):
    club_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    currency: Optional[str] = Field(default=None, min_length=1, max_length=8)
    voice_enabled: Optional[bool] = None
    warning_5_enabled: Optional[bool] = None
    warning_3_enabled: Optional[bool] = None
    warning_1_enabled: Optional[bool] = None
    expired_enabled: Optional[bool] = None


class SettingsOut(ORMModel):
    id: int
    club_name: str
    currency: str
    voice_enabled: bool
    warning_5_enabled: bool
    warning_3_enabled: bool
    warning_1_enabled: bool
    expired_enabled: bool


# ─────────────────────────────────────────────────────────────────────────────
# Analytics / reports
# ─────────────────────────────────────────────────────────────────────────────
class PeriodSummary(BaseModel):
    date_from: date
    date_to: date
    revenue: Decimal
    sessions: int
    transactions: int
    avg_check: Decimal
    play_seconds: int
    utilization: float  # percent of available station-time used
    # relative change vs the immediately preceding period of equal length (%)
    revenue_delta: Optional[float] = None
    sessions_delta: Optional[float] = None
    avg_check_delta: Optional[float] = None
    play_seconds_delta: Optional[float] = None


class SeriesPoint(BaseModel):
    label: str
    start: datetime
    revenue: Decimal
    sessions: int
    play_seconds: int


class RevenueSeries(BaseModel):
    bucket: str  # hour | day | week | month
    points: list[SeriesPoint]


class StationStat(BaseModel):
    station_id: int
    name: str
    number: int
    revenue: Decimal
    sessions: int
    play_seconds: int


class TariffStat(BaseModel):
    tariff_id: Optional[int] = None
    name: str
    revenue: Decimal
    sessions: int


class HeatmapCell(BaseModel):
    weekday: int  # 0 = Monday
    hour: int
    revenue: Decimal
    sessions: int


class SessionHistoryItem(BaseModel):
    id: int
    station_id: int
    station_name: str
    station_number: int
    tariff_name: str
    type: SessionType
    status: SessionStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: int
    total_paused_seconds: int
    price_snapshot: Decimal
    amount: Optional[Decimal] = None


class SessionHistoryPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SessionHistoryItem]


class PaymentItem(BaseModel):
    id: int
    created_at: datetime
    session_id: int
    station_name: str
    tariff_name: str
    amount: Decimal
    payment_type: TransactionType


class PaymentPage(BaseModel):
    total: int
    total_amount: Decimal
    page: int
    page_size: int
    items: list[PaymentItem]


class CleanupResult(BaseModel):
    deleted_sessions: int
    deleted_transactions: int
    older_than: datetime
    retention_days: int
