import pytest

from apps.bookings.models import Booking
from apps.bookings.state_machine import ALLOWED_TRANSITIONS, InvalidTransition, transition

from .factories import BookingFactory

S = Booking.Status

HAPPY_PATH = [
    (S.PENDING_PAYMENT, S.CONFIRMED),
    (S.CONFIRMED, S.ACTIVE),
    (S.ACTIVE, S.COMPLETED),
    (S.PENDING_PAYMENT, S.EXPIRED),
    (S.PENDING_PAYMENT, S.CANCELLED),
    (S.CONFIRMED, S.NO_SHOW),
    (S.EXPIRED, S.CONFIRMED),
]
FORBIDDEN = [
    (S.COMPLETED, S.ACTIVE),
    (S.COMPLETED, S.CONFIRMED),
    (S.CANCELLED, S.CONFIRMED),
    (S.EXPIRED, S.ACTIVE),
    (S.ACTIVE, S.PENDING_PAYMENT),
    (S.PENDING_PAYMENT, S.ACTIVE),
    (S.CONFIRMED, S.COMPLETED),
    (S.NO_SHOW, S.ACTIVE),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("start", "end"), HAPPY_PATH)
def test_valid_transitions_are_applied_and_saved(start, end):
    booking = BookingFactory(status=start)
    transition(booking, end)
    booking.refresh_from_db()
    assert booking.status == end


@pytest.mark.django_db
@pytest.mark.parametrize(("start", "end"), FORBIDDEN)
def test_invalid_transitions_raise_and_leave_status_unchanged(start, end):
    booking = BookingFactory(status=start)
    with pytest.raises(InvalidTransition):
        transition(booking, end)
    booking.refresh_from_db()
    assert booking.status == start


def test_cancelled_is_terminal():
    assert ALLOWED_TRANSITIONS[S.CANCELLED] == set()


def test_every_status_has_a_rule():
    assert set(ALLOWED_TRANSITIONS) == set(S)
