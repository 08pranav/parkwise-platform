from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .state_machine import transition


@shared_task
def expire_booking_lock(booking_id):
    from apps.bookings.models import Booking

    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(id=booking_id)
        except Booking.DoesNotExist:
            return

        if booking.status == Booking.Status.PENDING_PAYMENT:
            transition(booking, Booking.Status.EXPIRED)


@shared_task
def detect_no_shows():
    from apps.bookings.models import Booking
    from apps.societies.models import ParkingSlot

    now = timezone.now()

    with transaction.atomic():
        expired_bookings = Booking.objects.select_for_update().filter(
            status=Booking.Status.CONFIRMED,
            actual_entry__isnull=True,
            start_time__lte=now,
        )

        for booking in expired_bookings:
            halfway_point = booking.start_time + (booking.end_time - booking.start_time) / 2
            if now < halfway_point:
                continue

            transition(booking, Booking.Status.NO_SHOW)

            slot = ParkingSlot.objects.select_for_update().get(id=booking.slot_id)
            if slot.state == ParkingSlot.SlotState.RESERVED:
                slot.state = ParkingSlot.SlotState.AVAILABLE
                slot.save(update_fields=["state", "updated_at"])


@shared_task
def expire_stale_pending_bookings():
    """Backstop for ``expire_booking_lock``: expire every unpaid booking whose lock has run out.

    Idempotent: only rows still in ``pending_payment`` are touched, each under a row lock,
    so running it twice (or alongside the per-booking task) changes nothing the second time.
    """
    from apps.bookings.models import Booking

    now = timezone.now()
    ids = list(
        Booking.objects.filter(
            status=Booking.Status.PENDING_PAYMENT, lock_expires_at__lte=now
        ).values_list("id", flat=True)
    )
    expired = 0
    for booking_id in ids:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(id=booking_id)
            if booking.status == Booking.Status.PENDING_PAYMENT:
                transition(booking, Booking.Status.EXPIRED)
                expired += 1
    return expired
