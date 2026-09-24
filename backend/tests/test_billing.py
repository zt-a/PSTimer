"""Billing unit tests: exact per-second / per-minute pricing, no rounding."""

from decimal import Decimal

from app.services.billing import (
    calculate_fixed_price,
    calculate_open_price,
    rate_per_second,
)


PRICE = Decimal("300")


def test_fixed_price_exact():
    assert calculate_fixed_price(30, PRICE) == Decimal("150.00")
    assert calculate_fixed_price(60, PRICE) == Decimal("300.00")
    assert calculate_fixed_price(90, PRICE) == Decimal("450.00")
    assert calculate_fixed_price(120, PRICE) == Decimal("600.00")
    # odd duration is still exact
    assert calculate_fixed_price(1, PRICE) == Decimal("5.00")


def test_open_price_exact_to_the_second():
    # 300 / 3600 = 0.083333... per second
    assert rate_per_second(PRICE) == PRICE / Decimal("3600")
    assert calculate_open_price(60, PRICE) == Decimal("5.00")
    assert calculate_open_price(600, PRICE) == Decimal("50.00")
    assert calculate_open_price(3600, PRICE) == Decimal("300.00")
    assert calculate_open_price(450, PRICE) == Decimal("37.50")   # 7m30s
    assert calculate_open_price(10, PRICE) == Decimal("0.83")     # 10s
    assert calculate_open_price(1, PRICE) == Decimal("0.08")      # 1s
    assert calculate_open_price(0, PRICE) == Decimal("0.00")


def test_open_price_never_rounds_time_up():
    # exact seconds matter: 89 min must not become 90
    assert calculate_open_price(89 * 60, PRICE) == Decimal("445.00")
    assert calculate_open_price(70 * 60, PRICE) == Decimal("350.00")
