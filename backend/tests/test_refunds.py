import threading
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.db import connection
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.payments.models import Payment, Refund
from apps.payments.services import process_refund
from apps.societies.models import ParkingSlot

from .factories import BookingFactory, PaymentFactory, SlotFactory, SuperAdminFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def provider_settings(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_x"
    settings.RAZORPAY_KEY_ID = "rzp_test_x"
    settings.RAZORPAY_KEY_SECRET = "secret"


@pytest.fixture
def admin():
    return SuperAdminFactory()


@pytest.fixture
def paid():
    slot = SlotFactory(state=ParkingSlot.SlotState.RESERVED)
    booking = BookingFactory(slot=slot, status="confirmed")
    payment = PaymentFactory(
        booking=booking,
        status="captured",
        amount=Decimal("100.00"),
        stripe_payment_intent_id="pi_1",
    )
    return booking, payment, slot


def stripe_ok(refund_id="re_1"):
    return mock.patch("stripe.Refund.create", return_value=SimpleNamespace(id=refund_id))


def test_full_refund_settles_payment_booking_and_slot(paid, admin):
    booking, payment, slot = paid
    with stripe_ok():
        refund = process_refund(booking.id, Decimal("100.00"), "duplicate booking", admin)
    for obj in (booking, payment, slot):
        obj.refresh_from_db()
    assert refund.status == Refund.Status.SUCCEEDED
    assert refund.is_full_refund and refund.provider_refund_id == "re_1"
    assert refund.initiated_by == admin
    assert payment.status == Payment.Status.REFUNDED
    assert booking.status == Booking.Status.CANCELLED
    assert slot.state == ParkingSlot.SlotState.AVAILABLE


def test_partial_refund_before_start_keeps_the_booking_but_frees_the_slot(paid, admin):
    booking, payment, slot = paid
    with stripe_ok():
        refund = process_refund(booking.id, Decimal("40.00"), "goodwill", admin)
    for obj in (booking, payment, slot):
        obj.refresh_from_db()
    assert not refund.is_full_refund
    assert payment.status == Payment.Status.PARTIALLY_REFUNDED
    assert booking.status == Booking.Status.PARTIALLY_REFUNDED
    assert slot.state == ParkingSlot.SlotState.AVAILABLE  # driver had not arrived yet


def test_two_partial_refunds_can_add_up_to_a_full_refund(paid, admin):
    booking, payment, _ = paid
    with stripe_ok("re_a"):
        process_refund(booking.id, Decimal("40.00"), "first", admin)
    with stripe_ok("re_b"):
        process_refund(booking.id, Decimal("60.00"), "second", admin)
    payment.refresh_from_db()
    booking.refresh_from_db()
    assert payment.status == Payment.Status.REFUNDED
    assert booking.status == Booking.Status.CANCELLED


def test_cannot_refund_more_than_the_remaining_balance(paid, admin):
    booking, _, _ = paid
    with stripe_ok("re_a"):
        process_refund(booking.id, Decimal("70.00"), "first", admin)
    with pytest.raises(ValidationError, match="exceeds"):
        process_refund(booking.id, Decimal("40.00"), "too much", admin)


@pytest.mark.parametrize("amount", ["0", "-5"])
def test_amount_must_be_positive(paid, admin, amount):
    booking, _, _ = paid
    with pytest.raises(ValidationError, match="greater than zero"):
        process_refund(booking.id, Decimal(amount), "x", admin)


def test_unpaid_booking_cannot_be_refunded(admin):
    booking = BookingFactory(status="pending_payment")
    PaymentFactory(booking=booking, status="created")
    with pytest.raises(ValidationError, match="No captured payment"):
        process_refund(booking.id, Decimal("10"), "x", admin)


def test_gateway_failure_leaves_everything_unchanged_and_an_audit_row(paid, admin):
    booking, payment, slot = paid
    with (
        mock.patch("stripe.Refund.create", side_effect=RuntimeError("card network down")),
        pytest.raises(ValidationError),
    ):
        process_refund(booking.id, Decimal("100.00"), "oops", admin)
    for obj in (booking, payment, slot):
        obj.refresh_from_db()
    assert payment.status == Payment.Status.CAPTURED
    assert booking.status == Booking.Status.CONFIRMED
    assert slot.state == ParkingSlot.SlotState.RESERVED
    refund = Refund.objects.get(payment=payment)
    assert refund.status == Refund.Status.FAILED
    assert "gateway error" in refund.reason


def test_a_failed_attempt_does_not_use_up_the_refundable_balance(paid, admin):
    booking, _, _ = paid
    with (
        mock.patch("stripe.Refund.create", side_effect=RuntimeError("x")),
        pytest.raises(ValidationError),
    ):
        process_refund(booking.id, Decimal("100.00"), "first try", admin)
    with stripe_ok():
        refund = process_refund(booking.id, Decimal("100.00"), "retry", admin)
    assert refund.status == Refund.Status.SUCCEEDED


def test_stripe_call_carries_an_idempotency_key_tied_to_the_refund_row(paid, admin):
    booking, _, _ = paid
    with stripe_ok() as create:
        refund = process_refund(booking.id, Decimal("100.00"), "x", admin)
    assert create.call_args.kwargs["idempotency_key"] == f"refund-{refund.id}"
    assert create.call_args.kwargs["amount"] == 10000


def test_razorpay_refund_path(admin):
    booking = BookingFactory(status="confirmed")
    PaymentFactory(
        booking=booking,
        status="captured",
        amount=Decimal("50.00"),
        provider="razorpay",
        stripe_checkout_session_id=None,
        razorpay_order_id="order_1",
        razorpay_payment_id="pay_1",
    )
    fake_client = mock.MagicMock()
    fake_client.payment.refund.return_value = {"id": "rfnd_1"}
    with mock.patch("apps.payments.services.razorpay.Client", return_value=fake_client):
        refund = process_refund(booking.id, Decimal("50.00"), "x", admin)
    assert refund.provider_refund_id == "rfnd_1"
    fake_client.payment.refund.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_full_refunds_reach_the_gateway_once(admin):
    booking = BookingFactory(status="confirmed")
    PaymentFactory(
        booking=booking,
        status="captured",
        amount=Decimal("100.00"),
        stripe_payment_intent_id="pi_c",
    )
    calls = []

    def slow_create(**kwargs):
        calls.append(kwargs)
        time.sleep(0.3)  # keep the first refund in flight while the second one starts
        return SimpleNamespace(id="re_slow")

    outcomes = []
    barrier = threading.Barrier(2)

    def attempt():
        try:
            barrier.wait()
            process_refund(booking.id, Decimal("100.00"), "race", admin)
            outcomes.append("ok")
        except ValidationError:
            outcomes.append("rejected")
        finally:
            connection.close()

    with mock.patch("stripe.Refund.create", side_effect=slow_create):
        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert sorted(outcomes) == ["ok", "rejected"]
    assert len(calls) == 1
    assert Refund.objects.filter(status=Refund.Status.SUCCEEDED).count() == 1
