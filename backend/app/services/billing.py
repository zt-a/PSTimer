"""Billing service. Money is always Decimal - never float.

Billing is exact (no rounding of time):

  price_per_hour = 300

  OPEN  session: charged per second at price_per_hour / 3600.
                 7m30s -> 37.50, 10s -> 0.83
  FIXED session: charged for the purchased duration
                 (duration_minutes * price_per_hour / 60).

The final amount is rounded to 2 decimals (kopecks) with ROUND_HALF_UP.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, getcontext

getcontext().prec = 28

MONEY = Decimal("0.01")
SECONDS_PER_HOUR = Decimal("3600")


def rate_per_second(price_per_hour: Decimal) -> Decimal:
    """Per-second price at high precision (round only at the very end)."""
    return price_per_hour / SECONDS_PER_HOUR


def rate_per_minute(price_per_hour: Decimal) -> Decimal:
    """Per-minute price at high precision (round only at the very end)."""
    return price_per_hour / Decimal("60")


def _money(total: Decimal) -> Decimal:
    return total.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_open_price(elapsed_seconds: float, price_per_hour: Decimal) -> Decimal:
    """Exact price for an OPEN session from its elapsed time (in seconds)."""
    seconds = Decimal(str(max(elapsed_seconds, 0.0)))
    return _money(rate_per_second(price_per_hour) * seconds)


def calculate_fixed_price(duration_minutes: int, price_per_hour: Decimal) -> Decimal:
    """Exact price for a FIXED session from its purchased minutes."""
    return _money(rate_per_minute(price_per_hour) * Decimal(duration_minutes))
