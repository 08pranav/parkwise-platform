from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.tasks import detect_no_shows, expire_booking_lock, expire_stale_pending_bookings
from apps.societies.models import ParkingSlot

from .factories import BookingFactory, SlotFactory

pytestmark = pytest.mark.django_db


def test_expire_booking_lock_expires_an_unpaid_booking():
    booking = BookingFactory(status="pending_payment")
    expire_booking_lock(str(booking.id))
    booking.refresh_from_db()
    assert booking.status == Booking.Status.EXPIRED


def test_expire_booking_lock_is_idempotent_and_never_touches_paid_bookings():
    pending = BookingFactory(status="pending_payment")
    paid = BookingFactory(status="confirmed")
    for _ in range(3):
        expire_booking_lock(str(pending.id))
        expire_booking_lock(str(paid.id))
    pending.refresh_from_db()
    paid.refresh_from_db()
    assert pending.status == Booking.Status.EXPIRED
    assert paid.status == Booking.Status.CONFIRMED


def test_expire_booking_lock_ignores_unknown_ids():
    expire_booking_lock("00000000-0000-0000-0000-000000000000")


def test_sweep_expires_only_stale_pending_bookings():
    now = timezone.now()
    stale = BookingFactory(status="pending_payment", lock_expires_at=now - timedelta(minutes=1))
    fresh = BookingFactory(status="pending_payment", lock_expires_at=now + timedelta(minutes=4))
    paid = BookingFactory(status="confirmed", lock_expires_at=now - timedelta(minutes=1))
    assert expire_stale_pending_bookings() == 1
    for b in (stale, fresh, paid):
        b.refresh_from_db()
    assert (stale.status, fresh.status, paid.status) == ("expired", "pending_payment", "confirmed")


def test_sweep_is_idempotent():
    BookingFactory(status="pending_payment", lock_expires_at=timezone.now() - timedelta(minutes=1))
    assert expire_stale_pending_bookings() == 1
    assert expire_stale_pending_bookings() == 0


def test_no_show_after_the_halfway_point_frees_the_slot():
    slot = SlotFactory(state=ParkingSlot.SlotState.RESERVED)
    start = timezone.now() - timedelta(hours=2)
    booking = BookingFactory(
        slot=slot, status="confirmed", start_time=start, end_time=start + timedelta(hours=3)
    )
    detect_no_shows()
    booking.refresh_from_db()
    slot.refresh_from_db()
    assert booking.status == Booking.Status.NO_SHOW
    assert slot.state == ParkingSlot.SlotState.AVAILABLE


def test_no_show_waits_for_the_halfway_point_and_is_idempotent():
    start = timezone.now() - timedelta(minutes=10)
    early = BookingFactory(
        status="confirmed", start_time=start, end_time=start + timedelta(hours=3)
    )
    detect_no_shows()
    detect_no_shows()
    early.refresh_from_db()
    assert early.status == Booking.Status.CONFIRMED


def test_checked_in_bookings_are_never_marked_no_show():
    start = timezone.now() - timedelta(hours=2)
    booking = BookingFactory(
        status="confirmed",
        start_time=start,
        end_time=start + timedelta(hours=3),
        actual_entry=start + timedelta(minutes=5),
    )
    detect_no_shows()
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
