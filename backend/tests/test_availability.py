from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from apps.bookings.services import slot_is_available
from apps.societies.models import ParkingSlot

from .factories import BookingFactory, SlotFactory, WindowFactory

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")
MONDAY = date(2026, 11, 9)


def ist(day_offset, hour, minute=0):
    d = date.fromordinal(MONDAY.toordinal() + day_offset)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=IST)


def test_the_fixture_date_is_a_monday():
    assert MONDAY.weekday() == 0


@pytest.mark.django_db
def test_society_slot_without_windows_is_open_all_day():
    slot = SlotFactory()
    assert slot_is_available(slot, "car", ist(0, 3), ist(0, 5))


@pytest.mark.django_db
def test_resident_slot_without_windows_is_never_available():
    slot = SlotFactory(ownership_type=ParkingSlot.OwnershipType.RESIDENT)
    assert not slot_is_available(slot, "car", ist(0, 10), ist(0, 12))


@pytest.mark.django_db
def test_booking_must_fit_inside_the_window():
    slot = SlotFactory()
    WindowFactory(slot=slot, day_of_week=0, start_time="09:00", end_time="18:00")
    assert slot_is_available(slot, "car", ist(0, 10), ist(0, 12))
    assert not slot_is_available(slot, "car", ist(0, 17), ist(0, 19))
    assert not slot_is_available(slot, "car", ist(0, 8), ist(0, 10))


@pytest.mark.django_db
def test_utc_input_is_evaluated_in_ist():
    """10:00 IST is 04:30 UTC. The window is wall-clock IST, so this must fit."""
    slot = SlotFactory()
    WindowFactory(slot=slot, day_of_week=0, start_time="09:00", end_time="18:00")
    start = ist(0, 10).astimezone(UTC)
    end = ist(0, 12).astimezone(UTC)
    assert start.hour == 4
    assert slot_is_available(slot, "car", start, end)


@pytest.mark.django_db
def test_weekday_follows_local_time_not_utc():
    """00:30 IST Tuesday is 19:00 UTC Monday; it must use Tuesday's window."""
    slot = SlotFactory()
    WindowFactory(slot=slot, day_of_week=1, start_time="00:00", end_time="03:00")
    WindowFactory(slot=slot, day_of_week=0, start_time="09:00", end_time="10:00")
    start = ist(1, 0, 30).astimezone(UTC)
    end = ist(1, 2).astimezone(UTC)
    assert start.weekday() == 0  # still Monday in UTC
    assert slot_is_available(slot, "car", start, end)


@pytest.mark.django_db
def test_booking_crossing_midnight_needs_a_window_on_both_days():
    slot = SlotFactory()
    WindowFactory(slot=slot, day_of_week=0, start_time="20:00", end_time="23:59:59")
    WindowFactory(slot=slot, day_of_week=1, start_time="00:00", end_time="06:00")
    assert slot_is_available(slot, "car", ist(0, 22), ist(1, 2))


@pytest.mark.django_db
def test_midnight_crossing_fails_when_next_day_window_starts_later():
    slot = SlotFactory()
    WindowFactory(slot=slot, day_of_week=0, start_time="20:00", end_time="23:59:59")
    WindowFactory(slot=slot, day_of_week=1, start_time="03:00", end_time="06:00")
    assert not slot_is_available(slot, "car", ist(0, 22), ist(1, 2))


@pytest.mark.django_db
def test_resident_slot_cannot_cross_into_a_day_with_no_window():
    slot = SlotFactory(ownership_type=ParkingSlot.OwnershipType.RESIDENT)
    WindowFactory(slot=slot, day_of_week=0, start_time="20:00", end_time="23:59:59")
    assert not slot_is_available(slot, "car", ist(0, 22), ist(1, 1))


@pytest.mark.django_db
def test_blocked_slot_and_wrong_vehicle_type_are_unavailable():
    blocked = SlotFactory(state=ParkingSlot.SlotState.BLOCKED)
    assert not slot_is_available(blocked, "car", ist(0, 10), ist(0, 12))
    assert not slot_is_available(SlotFactory(), "bike", ist(0, 10), ist(0, 12))


@pytest.mark.django_db
def test_overlapping_booking_blocks_the_slot_but_an_adjacent_one_does_not():
    slot = SlotFactory()
    BookingFactory(slot=slot, status="confirmed", start_time=ist(0, 10), end_time=ist(0, 12))
    assert not slot_is_available(slot, "car", ist(0, 11), ist(0, 13))
    assert slot_is_available(slot, "car", ist(0, 12), ist(0, 14))
    assert slot_is_available(slot, "car", ist(0, 8), ist(0, 10))
