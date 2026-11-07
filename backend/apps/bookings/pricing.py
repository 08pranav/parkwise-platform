"""Deterministic surge pricing.

Pure functions only: the same inputs always give the same price, so the rules
are unit-testable without a database.

Rules (thresholds are strict ``>``):

* Own-society occupancy (bookings overlapping the window / active slots):
  above 80% adds +0.50, above 50% adds +0.20.
* Nearby-society occupancy (societies within roughly 5 km):
  above 80% adds +0.40, above 50% adds +0.20, above 30% adds +0.10.
* Multiplier = 1.00 + own-society surge + nearby surge, rounded to 2 places.
* Duration is billed in whole hours, rounded up.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

ONE = Decimal("1.00")
CENTS = Decimal("0.01")

OCCUPANCY_TIERS = (
    (Decimal("0.8"), Decimal("0.50")),
    (Decimal("0.5"), Decimal("0.20")),
)
NEARBY_TIERS = (
    (Decimal("0.8"), Decimal("0.40")),
    (Decimal("0.5"), Decimal("0.20")),
    (Decimal("0.3"), Decimal("0.10")),
)


def _tier_surge(rate, tiers):
    rate = Decimal(str(rate))
    for threshold, surge in tiers:
        if rate > threshold:
            return surge
    return Decimal("0.00")


def occupancy_rate(active_bookings, total_slots):
    return Decimal(active_bookings) / Decimal(max(total_slots, 1))


def surge_multiplier(own_rate, nearby_rate=None):
    multiplier = ONE + _tier_surge(own_rate, OCCUPANCY_TIERS)
    if nearby_rate is not None:
        multiplier += _tier_surge(nearby_rate, NEARBY_TIERS)
    return multiplier.quantize(CENTS, rounding=ROUND_HALF_UP)


def billable_hours(duration):
    return math.ceil(duration.total_seconds() / 3600)


def price(hourly_rate, duration, multiplier):
    """Return ``(base_amount, surge_amount, total)`` for a booking."""
    base = (Decimal(hourly_rate) * Decimal(billable_hours(duration))).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )
    surge = (base * (multiplier - ONE)).quantize(CENTS, rounding=ROUND_HALF_UP)
    return base, surge, base + surge
