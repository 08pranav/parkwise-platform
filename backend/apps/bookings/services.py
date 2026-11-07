import logging
import random
import string
import threading
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.societies.models import ParkingSlot, SlotAvailabilityWindow, Society
from utils.qr import generate_qr_token

from . import pricing
from .models import Booking
from .state_machine import transition

END_OF_DAY = time(23, 59, 59)  # the latest time a window can end
BUFFER_MINUTES = 10
MIN_DURATION_MINUTES = 30
MAX_DURATION_HOURS = 24
MAX_ADVANCE_HOURS = 24
LOCK_DURATION_SECONDS = 300  # 5 minutes
ACTIVE_BOOKING_STATUSES = [
    Booking.Status.PENDING_PAYMENT,
    Booking.Status.CONFIRMED,
    Booking.Status.ACTIVE,
]


def _booking_halfway_point(booking):
    return booking.start_time + (booking.end_time - booking.start_time) / 2


def _booking_blocks_user(booking, now):
    if booking.status == Booking.Status.PENDING_PAYMENT:
        return True

    if booking.status == Booking.Status.CONFIRMED:
        if booking.actual_entry is not None:
            return False
        return now <= _booking_halfway_point(booking)

    if booking.status == Booking.Status.ACTIVE:
        return booking.actual_exit is None

    return False


def _user_has_blocking_booking(user):
    now = timezone.now()
    bookings = Booking.objects.filter(
        user=user,
        status__in=ACTIVE_BOOKING_STATUSES,
    )
    return any(
        _booking_blocks_user(booking, now)
        for booking in bookings.only(
            "status",
            "actual_entry",
            "actual_exit",
            "start_time",
            "end_time",
        )
    )


def _generate_booking_number():
    date_part = timezone.now().strftime("%Y%m%d")
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{date_part}-{random_part}"


def validate_booking_window(start_time, end_time):
    now = timezone.now()

    # Allow a small 5-minute grace period for clock drift/delays
    if start_time < now - timedelta(minutes=5):
        raise ValidationError("Start time cannot be in the past.")

    if start_time > now + timedelta(hours=MAX_ADVANCE_HOURS):
        raise ValidationError(f"Cannot book more than {MAX_ADVANCE_HOURS} hours in advance.")

    duration = end_time - start_time
    if duration < timedelta(minutes=MIN_DURATION_MINUTES):
        raise ValidationError(f"Minimum booking duration is {MIN_DURATION_MINUTES} minutes.")

    if duration > timedelta(hours=MAX_DURATION_HOURS):
        raise ValidationError(f"Maximum booking duration is {MAX_DURATION_HOURS} hours.")

    return duration


def _active_windows(slot):
    prefetched = getattr(slot, "_prefetched_objects_cache", {})
    if "availability_windows" in prefetched:
        return [w for w in prefetched["availability_windows"] if w.is_active]
    return list(SlotAvailabilityWindow.objects.filter(slot=slot, is_active=True))


def _next_local_midnight(moment):
    return datetime.combine(moment.date() + timedelta(days=1), time.min, tzinfo=moment.tzinfo)


def _within_availability(slot, start_time, end_time):
    """True when every local-day slice of [start, end] fits the slot's windows.

    Windows are wall-clock times per weekday in the project time zone (IST), so
    the booking is converted to local time and split at local midnight. A booking
    that crosses midnight therefore needs a covering window on both days.
    A society-owned slot with no window on a given day is open all day;
    a resident-owned slot with no window on a day is closed.
    """
    windows = _active_windows(slot)
    cursor = timezone.localtime(start_time)
    local_end = timezone.localtime(end_time)
    while cursor < local_end:
        midnight = _next_local_midnight(cursor)
        slice_end = min(local_end, midnight)
        slice_end_time = END_OF_DAY if slice_end == midnight else slice_end.time()
        day_windows = [w for w in windows if w.day_of_week == cursor.weekday()]
        if day_windows:
            covered = any(
                w.start_time <= cursor.time() and w.end_time >= slice_end_time for w in day_windows
            )
            if not covered:
                return False
        elif slot.ownership_type == ParkingSlot.OwnershipType.RESIDENT:
            return False
        cursor = midnight
    return True


def slot_is_available(slot, vehicle_type, start_time, end_time):
    if slot.state == ParkingSlot.SlotState.BLOCKED:
        return False

    if slot.slot_type != vehicle_type:
        return False

    if not _within_availability(slot, start_time, end_time):
        return False

    now = timezone.now()
    overlapping = Booking.objects.filter(
        slot=slot,
        status__in=ACTIVE_BOOKING_STATUSES,
    ).filter(Q(start_time__lt=end_time) & Q(end_time__gt=start_time))
    return not any(
        _booking_blocks_user(booking, now)
        for booking in overlapping.only(
            "status",
            "actual_entry",
            "actual_exit",
            "start_time",
            "end_time",
        )
    )


def get_available_slots(*, society_id, vehicle_type, start_time, end_time, for_update=False):
    queryset = ParkingSlot.objects.filter(
        society_id=society_id,
        is_active=True,
        slot_type=vehicle_type,
    ).exclude(state=ParkingSlot.SlotState.BLOCKED)

    if for_update:
        queryset = queryset.select_for_update()

    slots = list(queryset.select_related("society").prefetch_related("availability_windows"))
    valid_slots = [
        slot for slot in slots if slot_is_available(slot, vehicle_type, start_time, end_time)
    ]
    valid_slots.sort(key=lambda slot: (slot.hourly_rate, slot.slot_number))
    return valid_slots


def _surge_for(slot, start_time, end_time):
    total_slots = ParkingSlot.objects.filter(society_id=slot.society_id, is_active=True).count()
    active_bookings = Booking.objects.filter(
        slot__society_id=slot.society_id,
        status__in=ACTIVE_BOOKING_STATUSES,
        end_time__gt=start_time,
        start_time__lt=end_time,
    ).count()
    own_rate = pricing.occupancy_rate(active_bookings, total_slots)

    nearby_rate = None
    society = slot.society
    if society.latitude and society.longitude:
        delta = Decimal("0.045")  # about 5 km
        nearby_ids = list(
            Society.objects.filter(
                latitude__isnull=False,
                longitude__isnull=False,
                latitude__range=(society.latitude - delta, society.latitude + delta),
                longitude__range=(society.longitude - delta, society.longitude + delta),
            )
            .exclude(id=slot.society_id)
            .values_list("id", flat=True)
        )
        if nearby_ids:
            nearby_slots = ParkingSlot.objects.filter(
                society_id__in=nearby_ids, is_active=True
            ).count()
            if nearby_slots:
                nearby_active = Booking.objects.filter(
                    slot__society_id__in=nearby_ids,
                    status__in=ACTIVE_BOOKING_STATUSES,
                    end_time__gt=start_time,
                    start_time__lt=end_time,
                ).count()
                nearby_rate = pricing.occupancy_rate(nearby_active, nearby_slots)

    return pricing.surge_multiplier(own_rate, nearby_rate)


def _enqueue_expiry(booking_id):
    """Queue the lock-expiry task without blocking the request if Redis is down."""
    from .tasks import expire_booking_lock

    def _send():
        try:
            expire_booking_lock.apply_async(args=[booking_id], countdown=LOCK_DURATION_SECONDS)
        except Exception as exc:  # the periodic sweep expires the booking anyway
            logging.getLogger(__name__).warning("Could not queue expiry task: %s", exc)

    threading.Thread(target=_send, daemon=True).start()


def _build_pending_booking(user, slot, vehicle, start_time, end_time):
    multiplier = _surge_for(slot, start_time, end_time)
    base_amount, surge_amount, amount = pricing.price(
        slot.hourly_rate, end_time - start_time, multiplier
    )

    booking_number = _generate_booking_number()
    booking = Booking.objects.create(
        booking_number=booking_number,
        user=user,
        vehicle=vehicle,
        slot=slot,
        start_time=start_time,
        end_time=end_time,
        status=Booking.Status.PENDING_PAYMENT,
        base_amount=base_amount,
        surge_amount=surge_amount,
        surge_multiplier=multiplier,
        amount=amount,
        qr_code_token=booking_number,
        lock_expires_at=timezone.now() + timedelta(seconds=LOCK_DURATION_SECONDS),
    )
    booking.qr_code_token = generate_qr_token(booking)
    booking.save(update_fields=["qr_code_token"])

    transaction.on_commit(lambda: _enqueue_expiry(str(booking.id)))
    return booking


def create_booking(user, slot_id, vehicle, start_time, end_time):
    validate_booking_window(start_time, end_time)

    with transaction.atomic():
        if _user_has_blocking_booking(user):
            raise ValidationError(
                "You already have an active parking booking. Please finish or cancel it before reserving another slot."
            )

        try:
            slot = (
                ParkingSlot.objects.select_for_update()
                .select_related("society")
                .prefetch_related("availability_windows")
                .get(id=slot_id, is_active=True)
            )
        except ParkingSlot.DoesNotExist:
            raise ValidationError("Slot not found or inactive.") from None

        if not slot_is_available(slot, vehicle.vehicle_type, start_time, end_time):
            raise ValidationError("Slot is not available for the requested time range.")

        if slot.approval_status != ParkingSlot.ApprovalStatus.APPROVED:
            raise ValidationError("Slot is not approved for booking yet.")

        if vehicle.vehicle_type != slot.slot_type:
            raise ValidationError(
                f"Vehicle type '{vehicle.vehicle_type}' does not match "
                f"slot type '{slot.slot_type}'."
            )

        return _build_pending_booking(user, slot, vehicle, start_time, end_time)


def create_booking_for_society(user, society_id, vehicle, start_time, end_time):
    validate_booking_window(start_time, end_time)

    with transaction.atomic():
        if _user_has_blocking_booking(user):
            raise ValidationError(
                "You already have an active parking booking. Please finish or cancel it before reserving another slot."
            )

        valid_slots = get_available_slots(
            society_id=society_id,
            vehicle_type=vehicle.vehicle_type,
            start_time=start_time,
            end_time=end_time,
            for_update=True,
        )
        if not valid_slots:
            raise ValidationError("No available slots found for the selected society.")

        return _build_pending_booking(
            user=user,
            slot=valid_slots[0],
            vehicle=vehicle,
            start_time=start_time,
            end_time=end_time,
        )


def cancel_booking(booking, user):
    if booking.user != user:
        raise ValidationError("You can only cancel your own bookings.")

    if booking.status not in (
        Booking.Status.PENDING_PAYMENT,
        Booking.Status.CONFIRMED,
    ):
        raise ValidationError(f"Cannot cancel booking in '{booking.status}' state.")

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(id=booking.id)
        was_confirmed = booking.status == Booking.Status.CONFIRMED

        transition(booking, Booking.Status.CANCELLED)

        # Free slot if it was reserved
        if was_confirmed:
            slot = ParkingSlot.objects.select_for_update().get(id=booking.slot_id)
            if slot.state == ParkingSlot.SlotState.RESERVED:
                slot.state = ParkingSlot.SlotState.AVAILABLE
                slot.save(update_fields=["state", "updated_at"])

    return booking
