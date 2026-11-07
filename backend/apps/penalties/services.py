import math
from decimal import ROUND_HALF_UP, Decimal

from .models import Penalty

# Overstay penalty: 20% of the booking amount for every started hour of overstay.
OVERSTAY_PENALTY_RATE = Decimal("0.20")


def overstay_minutes(end_time, exit_time):
    """Whole minutes past ``end_time``, rounded up; 0 when the exit was on time.

    Both arguments are timezone-aware, so the result does not depend on the
    display time zone (the database stores UTC, the apps show IST).
    """
    seconds = (exit_time - end_time).total_seconds()
    return max(0, math.ceil(seconds / 60))


def penalty_amount(booking_amount, minutes):
    hours = math.ceil(minutes / 60)
    return (Decimal(booking_amount) * OVERSTAY_PENALTY_RATE * hours).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def create_overstay_penalty(booking, minutes):
    """Create the overstay penalty for ``booking``; calling it again returns the same penalty."""
    penalty, _ = Penalty.objects.get_or_create(
        booking=booking,
        defaults={
            "user": booking.user,
            "overstay_minutes": minutes,
            "amount": penalty_amount(booking.amount, minutes),
        },
    )
    return {
        "penalty_id": str(penalty.id),
        "amount": str(penalty.amount),
        "overstay_minutes": penalty.overstay_minutes,
        "overstay_hours": math.ceil(penalty.overstay_minutes / 60),
    }
