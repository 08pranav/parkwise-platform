"""Booking lifecycle rules.

Status names map onto the lifecycle like this:

    pending_payment -> confirmed (paid) -> active (checked in) -> completed
    pending_payment -> expired | cancelled
    confirmed       -> cancelled | no_show
    any paid state  -> partially_refunded | cancelled (full refund)
    expired         -> confirmed (a payment that arrives after the lock expired,
                       when the slot is still free)

Every status change in the codebase goes through :func:`transition`, so an
invalid jump (for example completed -> active) raises instead of corrupting data.
"""

from rest_framework.exceptions import ValidationError

from .models import Booking

S = Booking.Status

ALLOWED_TRANSITIONS = {
    S.PENDING_PAYMENT: {S.CONFIRMED, S.EXPIRED, S.CANCELLED},
    S.CONFIRMED: {S.ACTIVE, S.CANCELLED, S.NO_SHOW, S.PARTIALLY_REFUNDED},
    S.ACTIVE: {S.COMPLETED, S.CANCELLED, S.PARTIALLY_REFUNDED},
    S.COMPLETED: {S.CANCELLED, S.PARTIALLY_REFUNDED},
    S.NO_SHOW: {S.CANCELLED, S.PARTIALLY_REFUNDED},
    S.EXPIRED: {S.CONFIRMED},
    S.PARTIALLY_REFUNDED: {S.CANCELLED},
    S.CANCELLED: set(),
}


class InvalidTransition(ValidationError):
    pass


def can_transition(current, target):
    return target in ALLOWED_TRANSITIONS.get(current, set())


def transition(booking, target, **fields):
    """Move ``booking`` to ``target`` and persist it, optionally setting other fields.

    Callers must hold a row lock (``select_for_update``) on the booking.
    """
    if not can_transition(booking.status, target):
        raise InvalidTransition(f"Cannot move a booking from '{booking.status}' to '{target}'.")
    booking.status = target
    for name, value in fields.items():
        setattr(booking, name, value)
    booking.save(update_fields=["status", "updated_at", *fields])
    return booking
