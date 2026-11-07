from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.penalties.models import Penalty
from apps.qr_validation.models import ScanEvent
from apps.qr_validation.services import validate_entry, validate_exit
from apps.societies.models import ParkingSlot

from .factories import BookingFactory, GuardFactory, SlotFactory, SocietyFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def gate():
    society = SocietyFactory()
    return society, GuardFactory(society=society), SlotFactory(society=society)


def booking_for(slot, *, started=10, length=120, **kwargs):
    now = timezone.now()
    return BookingFactory(
        slot=slot,
        start_time=now - timedelta(minutes=started),
        end_time=now - timedelta(minutes=started) + timedelta(minutes=length),
        **kwargs,
    )


def last_event():
    return ScanEvent.objects.latest("scanned_at")


class TestEntry:
    def test_valid_scan_checks_the_driver_in(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, status="confirmed")
        result = validate_entry(booking.qr_code_token, guard)
        booking.refresh_from_db()
        slot.refresh_from_db()
        assert result["status"] == "entry_granted"
        assert booking.status == Booking.Status.ACTIVE and booking.actual_entry
        assert slot.state == ParkingSlot.SlotState.OCCUPIED
        assert last_event().result == ScanEvent.Result.APPROVED

    def test_second_scan_of_the_same_qr_is_rejected_and_logged(self, gate):
        """Replay protection: a booking admits one entry."""
        _, guard, slot = gate
        booking = booking_for(slot, status="confirmed")
        validate_entry(booking.qr_code_token, guard)
        with pytest.raises(ValidationError, match="Only confirmed"):
            validate_entry(booking.qr_code_token, guard)
        assert last_event().result == ScanEvent.Result.DENIED
        assert ScanEvent.objects.filter(result="approved").count() == 1

    def test_garbage_and_forged_tokens_are_denied_and_logged(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, status="confirmed")
        for token in ("not-a-token", booking.qr_code_token[:-3] + "abc"):
            with pytest.raises(ValidationError, match="Invalid QR"):
                validate_entry(token, guard)
        assert ScanEvent.objects.filter(booking__isnull=True, result="denied").count() == 2

    def test_a_valid_token_that_is_not_the_stored_one_is_rejected(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, status="confirmed")
        stale = booking.qr_code_token
        Booking.objects.filter(id=booking.id).update(qr_code_token="rotated")
        with pytest.raises(ValidationError, match="not found"):
            validate_entry(stale, guard)

    def test_other_societies_bookings_are_denied(self, gate):
        _, guard, _ = gate
        booking = booking_for(SlotFactory(), status="confirmed")
        with pytest.raises(ValidationError, match="does not belong to your society"):
            validate_entry(booking.qr_code_token, guard)
        assert last_event().booking == booking

    def test_unpaid_bookings_are_denied(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, status="pending_payment")
        with pytest.raises(ValidationError, match="Only confirmed"):
            validate_entry(booking.qr_code_token, guard)

    def test_early_arrival_is_denied(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, started=-30, status="confirmed")
        with pytest.raises(ValidationError, match="Early arrival"):
            validate_entry(booking.qr_code_token, guard)

    def test_entry_after_the_booking_ended_is_denied(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, started=180, length=120, status="confirmed")
        with pytest.raises(ValidationError, match="expired"):
            validate_entry(booking.qr_code_token, guard)

    def test_entry_after_the_halfway_point_counts_as_no_show(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, started=90, length=120, status="confirmed")
        with pytest.raises(ValidationError, match="no-show"):
            validate_entry(booking.qr_code_token, guard)

    @pytest.mark.parametrize("state", ["completed", "cancelled", "expired", "no_show"])
    def test_final_state_bookings_are_denied(self, gate, state):
        _, guard, slot = gate
        booking = booking_for(slot, status=state)
        with pytest.raises(ValidationError):
            validate_entry(booking.qr_code_token, guard)


class TestExit:
    def checked_in(self, slot, **kwargs):
        booking = booking_for(slot, status="confirmed", **kwargs)
        return booking

    def test_on_time_exit_completes_without_a_penalty(self, gate):
        _, guard, slot = gate
        booking = self.checked_in(slot)
        validate_entry(booking.qr_code_token, guard)
        result = validate_exit(booking.qr_code_token, guard)
        booking.refresh_from_db()
        slot.refresh_from_db()
        assert result["status"] == "exit_granted" and result["overstay"] is False
        assert booking.status == Booking.Status.COMPLETED and booking.actual_exit
        assert slot.state == ParkingSlot.SlotState.AVAILABLE
        assert not Penalty.objects.exists()

    def test_overstay_creates_a_penalty_in_the_same_transaction(self, gate):
        _, guard, slot = gate
        booking = self.checked_in(slot, started=190, length=180)  # ended 10 minutes ago
        Booking.objects.filter(id=booking.id).update(
            status="active", actual_entry=timezone.now() - timedelta(minutes=185)
        )
        result = validate_exit(booking.qr_code_token, guard)
        penalty = Penalty.objects.get(booking=booking)
        assert result["overstay"] is True
        assert penalty.overstay_minutes in (10, 11)
        assert penalty.amount == booking.amount * Decimal("0.20")
        assert result["penalty"]["penalty_id"] == str(penalty.id)

    def test_just_a_few_seconds_late_still_costs_one_started_hour(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, started=60, length=60, status="active")
        Booking.objects.filter(id=booking.id).update(
            end_time=timezone.now() - timedelta(seconds=20)
        )
        validate_exit(booking.qr_code_token, guard)
        penalty = Penalty.objects.get(booking=booking)
        assert penalty.overstay_minutes == 1
        assert penalty.amount > 0

    def test_second_exit_scan_is_rejected_and_adds_no_second_penalty(self, gate):
        _, guard, slot = gate
        booking = booking_for(slot, started=190, length=180, status="active")
        validate_exit(booking.qr_code_token, guard)
        with pytest.raises(ValidationError, match="Only active"):
            validate_exit(booking.qr_code_token, guard)
        assert Penalty.objects.filter(booking=booking).count() == 1

    def test_exit_requires_a_prior_entry(self, gate):
        _, guard, slot = gate
        booking = self.checked_in(slot)
        with pytest.raises(ValidationError, match="Only active"):
            validate_exit(booking.qr_code_token, guard)

    def test_exit_in_another_society_is_denied(self, gate):
        _, guard, _ = gate
        booking = booking_for(SlotFactory(), status="active")
        with pytest.raises(ValidationError, match="does not belong"):
            validate_exit(booking.qr_code_token, guard)

    def test_invalid_exit_token_is_logged(self, gate):
        _, guard, _ = gate
        with pytest.raises(ValidationError, match="Invalid QR"):
            validate_exit("nope", guard)
        assert last_event().event_type == ScanEvent.EventType.EXIT
