from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, transaction

from apps.penalties.models import Penalty
from apps.penalties.services import create_overstay_penalty, overstay_minutes, penalty_amount

from .factories import BookingFactory

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")


def test_on_time_exit_has_no_overstay():
    end = datetime(2026, 11, 9, 12, 0, tzinfo=IST)
    assert overstay_minutes(end, end) == 0
    assert overstay_minutes(end, end - timedelta(minutes=5)) == 0


@pytest.mark.parametrize(
    ("seconds", "minutes"), [(1, 1), (30, 1), (60, 1), (61, 2), (3600, 60), (3601, 61)]
)
def test_overstay_minutes_round_up(seconds, minutes):
    end = datetime(2026, 11, 9, 12, 0, tzinfo=IST)
    assert overstay_minutes(end, end + timedelta(seconds=seconds)) == minutes


def test_result_is_the_same_in_utc_and_ist():
    end_ist = datetime(2026, 11, 9, 12, 0, tzinfo=IST)
    exit_ist = end_ist + timedelta(minutes=45)
    assert overstay_minutes(end_ist, exit_ist) == overstay_minutes(
        end_ist.astimezone(UTC), exit_ist.astimezone(UTC)
    )


def test_overstay_across_local_midnight():
    end = datetime(2026, 11, 9, 23, 50, tzinfo=IST)
    exit_ = datetime(2026, 11, 10, 0, 20, tzinfo=IST)
    assert overstay_minutes(end, exit_) == 30


@pytest.mark.parametrize(
    ("minutes", "amount"),
    [(1, "12.00"), (60, "12.00"), (61, "24.00"), (150, "36.00")],
)
def test_penalty_is_20_percent_of_the_booking_per_started_hour(minutes, amount):
    assert penalty_amount(Decimal("60.00"), minutes) == Decimal(amount)


@pytest.mark.django_db
def test_creating_the_penalty_twice_returns_the_same_one():
    booking = BookingFactory(status="completed")
    first = create_overstay_penalty(booking, 30)
    second = create_overstay_penalty(booking, 90)
    assert first["penalty_id"] == second["penalty_id"]
    assert Penalty.objects.filter(booking=booking).count() == 1


@pytest.mark.django_db
def test_database_rejects_a_second_penalty_for_one_booking():
    booking = BookingFactory(status="completed")
    Penalty.objects.create(booking=booking, user=booking.user, overstay_minutes=5, amount=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Penalty.objects.create(booking=booking, user=booking.user, overstay_minutes=9, amount=2)
