from datetime import timedelta
from decimal import Decimal

import pytest

from apps.bookings import pricing


@pytest.mark.parametrize(
    ("own_rate", "expected"),
    [
        ("0.00", "1.00"),
        ("0.50", "1.00"),  # thresholds are strict: exactly 50% is not surge
        ("0.51", "1.20"),
        ("0.80", "1.20"),
        ("0.81", "1.50"),
        ("1.50", "1.50"),
    ],
)
def test_own_society_tiers(own_rate, expected):
    assert pricing.surge_multiplier(Decimal(own_rate)) == Decimal(expected)


@pytest.mark.parametrize(
    ("nearby_rate", "expected"),
    [("0.30", "1.00"), ("0.31", "1.10"), ("0.50", "1.10"), ("0.51", "1.20"), ("0.81", "1.40")],
)
def test_nearby_tiers(nearby_rate, expected):
    assert pricing.surge_multiplier(Decimal("0"), Decimal(nearby_rate)) == Decimal(expected)


def test_tiers_stack_to_a_maximum_of_1_90():
    assert pricing.surge_multiplier(Decimal("0.9"), Decimal("0.9")) == Decimal("1.90")


def test_no_nearby_data_means_no_nearby_surge():
    assert pricing.surge_multiplier(Decimal("0.6"), None) == Decimal("1.20")


def test_same_inputs_always_give_same_price():
    args = (Decimal("30.00"), timedelta(hours=2), Decimal("1.50"))
    assert pricing.price(*args) == pricing.price(*args)


def test_price_breakdown():
    base, surge, total = pricing.price(Decimal("30.00"), timedelta(hours=2), Decimal("1.50"))
    assert (base, surge, total) == (Decimal("60.00"), Decimal("30.00"), Decimal("90.00"))


@pytest.mark.parametrize(
    ("minutes", "hours"), [(30, 1), (60, 1), (61, 2), (120, 2), (121, 3), (24 * 60, 24)]
)
def test_duration_is_billed_in_whole_hours_rounded_up(minutes, hours):
    assert pricing.billable_hours(timedelta(minutes=minutes)) == hours


def test_occupancy_rate_with_no_slots_does_not_divide_by_zero():
    assert pricing.occupancy_rate(0, 0) == Decimal("0")


def test_rounding_is_half_up_to_two_places():
    base, surge, total = pricing.price(Decimal("33.33"), timedelta(hours=1), Decimal("1.20"))
    assert (base, surge, total) == (Decimal("33.33"), Decimal("6.67"), Decimal("40.00"))
