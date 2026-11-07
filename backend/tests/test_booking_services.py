from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.bookings.services import (
    cancel_booking,
    create_booking,
    create_booking_for_society,
    get_available_slots,
    validate_booking_window,
)
from apps.societies.models import ParkingSlot

from .factories import BookingFactory, SlotFactory, SocietyFactory, UserFactory, VehicleFactory


def window(start_min=10, hours=2):
    start = timezone.now() + timedelta(minutes=start_min)
    return start, start + timedelta(hours=hours)


class TestValidateWindow:
    def test_accepts_a_normal_window(self):
        assert validate_booking_window(*window()) == timedelta(hours=2)

    def test_allows_five_minutes_of_clock_drift(self):
        start = timezone.now() - timedelta(minutes=4)
        validate_booking_window(start, start + timedelta(hours=1))

    def test_rejects_start_in_the_past(self):
        start = timezone.now() - timedelta(minutes=30)
        with pytest.raises(ValidationError, match="past"):
            validate_booking_window(start, start + timedelta(hours=1))

    def test_rejects_more_than_24_hours_in_advance(self):
        start = timezone.now() + timedelta(hours=25)
        with pytest.raises(ValidationError, match="in advance"):
            validate_booking_window(start, start + timedelta(hours=1))

    def test_rejects_under_30_minutes_and_over_24_hours(self):
        start = timezone.now() + timedelta(minutes=5)
        with pytest.raises(ValidationError, match="Minimum"):
            validate_booking_window(start, start + timedelta(minutes=29))
        with pytest.raises(ValidationError, match="Maximum"):
            validate_booking_window(start, start + timedelta(hours=25))


@pytest.mark.django_db
class TestCreateBooking:
    def test_creates_a_pending_booking_with_price_and_qr(self, user, vehicle, slot):
        start, end = window()
        booking = create_booking(user, slot.id, vehicle, start, end)
        assert booking.status == Booking.Status.PENDING_PAYMENT
        assert booking.base_amount == Decimal("60.00")
        assert booking.surge_multiplier == Decimal("1.00")
        assert booking.amount == Decimal("60.00")
        assert booking.lock_expires_at > timezone.now()
        assert booking.qr_code_token != booking.booking_number  # replaced by a signed token

    def test_surge_applies_when_the_society_is_busy(self, user, vehicle, society):
        slot = SlotFactory(society=society)
        start, end = window()
        # three slots in the society, two already booked: 2 / 3 = 67% occupancy (> 50%)
        for _ in range(2):
            BookingFactory(
                slot=SlotFactory(society=society),
                start_time=start,
                end_time=end,
                status="confirmed",
            )
        booking = create_booking(user, slot.id, vehicle, start, end)
        assert booking.surge_multiplier == Decimal("1.20")
        assert booking.amount == Decimal("72.00")

    def test_nearby_busy_societies_add_area_demand_surge(self, user, vehicle):
        here = SocietyFactory(latitude=Decimal("18.9300"), longitude=Decimal("72.8300"))
        neighbour = SocietyFactory(latitude=Decimal("18.9400"), longitude=Decimal("72.8400"))
        far_away = SocietyFactory(latitude=Decimal("19.5000"), longitude=Decimal("73.5000"))
        slot = SlotFactory(society=here)
        start, end = window()
        # the neighbour's only slot is booked (100% > 80%); a far-away busy society is ignored
        BookingFactory(
            slot=SlotFactory(society=neighbour), start_time=start, end_time=end, status="confirmed"
        )
        BookingFactory(
            slot=SlotFactory(society=far_away), start_time=start, end_time=end, status="confirmed"
        )
        booking = create_booking(user, slot.id, vehicle, start, end)
        assert booking.surge_multiplier == Decimal("1.40")
        assert booking.surge_amount == Decimal("24.00")

    def test_overlapping_booking_on_the_same_slot_is_rejected(self, user, vehicle, slot):
        start, end = window()
        create_booking(user, slot.id, vehicle, start, end)
        other = UserFactory(society=slot.society)
        with pytest.raises(ValidationError, match="not available"):
            create_booking(other, slot.id, VehicleFactory(user=other), start, end)

    def test_adjacent_booking_on_the_same_slot_is_accepted(self, user, vehicle, slot):
        start, end = window()
        create_booking(user, slot.id, vehicle, start, end)
        other = UserFactory(society=slot.society)
        second = create_booking(
            other, slot.id, VehicleFactory(user=other), end, end + timedelta(hours=1)
        )
        assert second.status == Booking.Status.PENDING_PAYMENT

    def test_a_user_cannot_hold_two_blocking_bookings(self, user, vehicle, society):
        start, end = window()
        create_booking(user, SlotFactory(society=society).id, vehicle, start, end)
        with pytest.raises(ValidationError, match="already have an active"):
            create_booking(user, SlotFactory(society=society).id, vehicle, start, end)

    def test_vehicle_type_must_match_the_slot(self, user, society):
        bike = VehicleFactory(user=user, vehicle_type="bike")
        start, end = window()
        with pytest.raises(ValidationError):
            create_booking(user, SlotFactory(society=society).id, bike, start, end)

    def test_unapproved_slot_cannot_be_booked(self, user, vehicle, society):
        slot = SlotFactory(society=society, approval_status=ParkingSlot.ApprovalStatus.PENDING)
        with pytest.raises(ValidationError, match="not approved"):
            create_booking(user, slot.id, vehicle, *window())

    def test_inactive_slot_is_reported_as_not_found(self, user, vehicle, society):
        slot = SlotFactory(society=society, is_active=False)
        with pytest.raises(ValidationError, match="not found"):
            create_booking(user, slot.id, vehicle, *window())

    def test_society_booking_picks_the_cheapest_free_slot(self, user, vehicle, society):
        SlotFactory(society=society, hourly_rate=Decimal("50"))
        cheap = SlotFactory(society=society, hourly_rate=Decimal("20"))
        booking = create_booking_for_society(user, society.id, vehicle, *window())
        assert booking.slot_id == cheap.id

    def test_society_booking_with_nothing_free_fails(self, user, vehicle, society):
        with pytest.raises(ValidationError, match="No available slots"):
            create_booking_for_society(user, society.id, vehicle, *window())


@pytest.mark.django_db
class TestAvailableSlots:
    def test_lists_only_free_matching_slots_sorted_by_price(self, society):
        a = SlotFactory(society=society, hourly_rate=Decimal("40"))
        b = SlotFactory(society=society, hourly_rate=Decimal("10"))
        SlotFactory(society=society, slot_type="bike")
        taken = SlotFactory(society=society)
        start, end = window()
        BookingFactory(slot=taken, start_time=start, end_time=end, status="confirmed")
        slots = get_available_slots(
            society_id=society.id, vehicle_type="car", start_time=start, end_time=end
        )
        assert [s.id for s in slots] == [b.id, a.id]


@pytest.mark.django_db
class TestCancel:
    def test_pending_booking_can_be_cancelled(self, user):
        booking = BookingFactory(user=user, status="pending_payment")
        cancel_booking(booking, user)
        booking.refresh_from_db()
        assert booking.status == Booking.Status.CANCELLED

    def test_cancelling_a_confirmed_booking_frees_the_reserved_slot(self, user):
        slot = SlotFactory(state=ParkingSlot.SlotState.RESERVED)
        booking = BookingFactory(user=user, slot=slot, status="confirmed")
        cancel_booking(booking, user)
        slot.refresh_from_db()
        assert slot.state == ParkingSlot.SlotState.AVAILABLE

    def test_only_the_owner_can_cancel(self, user):
        booking = BookingFactory(user=user, status="confirmed")
        with pytest.raises(ValidationError, match="your own"):
            cancel_booking(booking, UserFactory())

    @pytest.mark.parametrize("state", ["active", "completed", "cancelled", "expired", "no_show"])
    def test_cannot_cancel_after_entry_or_in_a_final_state(self, user, state):
        booking = BookingFactory(user=user, status=state)
        with pytest.raises(ValidationError, match="Cannot cancel"):
            cancel_booking(booking, user)
