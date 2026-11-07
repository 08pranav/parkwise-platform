import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest import mock

import pytest
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.payments.models import Payment, PaymentEvent, Refund
from apps.payments.services import handle_razorpay_webhook, handle_stripe_webhook
from apps.societies.models import ParkingSlot

from .factories import BookingFactory, PaymentFactory, SlotFactory

pytestmark = pytest.mark.django_db

STRIPE_SECRET = "whsec_test_secret"
RAZORPAY_SECRET = "rzp_whsec_test"


@pytest.fixture(autouse=True)
def provider_settings(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_x"
    settings.STRIPE_WEBHOOK_SECRET = STRIPE_SECRET
    settings.RAZORPAY_WEBHOOK_SECRET = RAZORPAY_SECRET
    settings.RAZORPAY_KEY_ID = "rzp_test_x"
    settings.RAZORPAY_KEY_SECRET = "secret"


def stripe_event(event_id, event_type, object_id):
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "data": {"object": {"id": object_id}},
        }
    )


def stripe_signature(payload, secret=STRIPE_SECRET):
    ts = int(time.time())
    digest = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def paid_session(intent="pi_123"):
    return SimpleNamespace(payment_status="paid", currency="inr", payment_intent=intent)


@pytest.fixture
def pending():
    slot = SlotFactory()
    booking = BookingFactory(slot=slot, status="pending_payment")
    payment = PaymentFactory(booking=booking, stripe_checkout_session_id="cs_1")
    return booking, payment, slot


def deliver_stripe(event_id, event_type, object_id, retrieve=None):
    payload = stripe_event(event_id, event_type, object_id)
    with mock.patch("stripe.checkout.Session.retrieve", return_value=retrieve or paid_session()):
        return handle_stripe_webhook(payload, stripe_signature(payload))


class TestStripeWebhook:
    def test_completed_checkout_confirms_booking_and_reserves_slot(self, pending):
        booking, payment, slot = pending
        assert deliver_stripe("evt_1", "checkout.session.completed", "cs_1") == "processed"
        for obj in (booking, payment, slot):
            obj.refresh_from_db()
        assert payment.status == Payment.Status.CAPTURED
        assert payment.stripe_payment_intent_id == "pi_123"
        assert booking.status == Booking.Status.CONFIRMED
        assert slot.state == ParkingSlot.SlotState.RESERVED

    def test_duplicate_delivery_is_ignored(self, pending):
        booking, payment, _ = pending
        deliver_stripe("evt_1", "checkout.session.completed", "cs_1")
        assert deliver_stripe("evt_1", "checkout.session.completed", "cs_1") == "duplicate"
        assert PaymentEvent.objects.filter(event_id="evt_1").count() == 1

    def test_a_new_event_for_an_already_captured_payment_changes_nothing(self, pending):
        booking, payment, _ = pending
        deliver_stripe("evt_1", "checkout.session.completed", "cs_1")
        deliver_stripe("evt_2", "checkout.session.completed", "cs_1")
        booking.refresh_from_db()
        assert booking.status == Booking.Status.CONFIRMED
        assert Payment.objects.get(id=payment.id).status == Payment.Status.CAPTURED

    def test_forged_signature_is_rejected_and_nothing_is_recorded(self, pending):
        payload = stripe_event("evt_x", "checkout.session.completed", "cs_1")
        with pytest.raises(ValidationError, match="signature"):
            handle_stripe_webhook(payload, stripe_signature(payload, secret="whsec_wrong"))
        assert not PaymentEvent.objects.exists()

    def test_missing_signature_header_is_rejected(self, pending):
        payload = stripe_event("evt_x", "checkout.session.completed", "cs_1")
        with pytest.raises(ValidationError):
            handle_stripe_webhook(payload, "")

    def test_without_a_configured_secret_the_endpoint_fails_closed(self, pending, settings):
        settings.STRIPE_WEBHOOK_SECRET = ""
        payload = stripe_event("evt_x", "checkout.session.completed", "cs_1")
        with pytest.raises(ValidationError, match="not configured"):
            handle_stripe_webhook(payload, "anything")

    def test_payment_failed_never_downgrades_a_captured_payment(self, pending):
        _, payment, _ = pending
        deliver_stripe("evt_1", "checkout.session.completed", "cs_1")
        Payment.objects.filter(id=payment.id).update(stripe_payment_intent_id="pi_123")
        deliver_stripe("evt_2", "payment_intent.payment_failed", "pi_123")
        assert Payment.objects.get(id=payment.id).status == Payment.Status.CAPTURED

    def test_payment_failed_marks_a_waiting_payment_failed(self, pending):
        _, payment, _ = pending
        Payment.objects.filter(id=payment.id).update(stripe_payment_intent_id="pi_9")
        deliver_stripe("evt_f", "payment_intent.payment_failed", "pi_9")
        assert Payment.objects.get(id=payment.id).status == Payment.Status.FAILED

    def test_out_of_order_events_still_end_captured(self, pending):
        """A failure event delivered before the success event must not block capture."""
        booking, payment, _ = pending
        Payment.objects.filter(id=payment.id).update(stripe_payment_intent_id="pi_123")
        deliver_stripe("evt_f", "payment_intent.payment_failed", "pi_123")
        deliver_stripe("evt_ok", "checkout.session.completed", "cs_1")
        booking.refresh_from_db()
        assert Payment.objects.get(id=payment.id).status == Payment.Status.CAPTURED
        assert booking.status == Booking.Status.CONFIRMED

    def test_failed_processing_rolls_back_the_event_so_the_retry_is_processed(self, pending):
        payload = stripe_event("evt_r", "checkout.session.completed", "cs_1")
        with (
            mock.patch("stripe.checkout.Session.retrieve", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            handle_stripe_webhook(payload, stripe_signature(payload))
        assert not PaymentEvent.objects.filter(event_id="evt_r").exists()
        assert deliver_stripe("evt_r", "checkout.session.completed", "cs_1") == "processed"

    def test_unpaid_session_does_not_confirm(self, pending):
        booking, _, _ = pending
        unpaid = SimpleNamespace(payment_status="unpaid", currency="inr", payment_intent=None)
        with pytest.raises(ValidationError):
            deliver_stripe("evt_u", "checkout.session.completed", "cs_1", retrieve=unpaid)
        booking.refresh_from_db()
        assert booking.status == Booking.Status.PENDING_PAYMENT


def razorpay_body(event, order_id="order_1", payment_id="pay_1"):
    return json.dumps(
        {
            "event": event,
            "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id}}},
        }
    ).encode()


def razorpay_sig(body, secret=RAZORPAY_SECRET):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def rz_pending():
    booking = BookingFactory(status="pending_payment")
    payment = PaymentFactory(
        booking=booking,
        provider="razorpay",
        stripe_checkout_session_id=None,
        razorpay_order_id="order_1",
    )
    return booking, payment


class TestRazorpayWebhook:
    def test_captured_event_confirms_the_booking(self, rz_pending):
        booking, payment = rz_pending
        body = razorpay_body("payment.captured")
        assert handle_razorpay_webhook(body, razorpay_sig(body), "evt_a") == "processed"
        booking.refresh_from_db()
        payment.refresh_from_db()
        assert booking.status == Booking.Status.CONFIRMED
        assert payment.razorpay_payment_id == "pay_1"

    def test_duplicate_event_id_is_ignored(self, rz_pending):
        body = razorpay_body("payment.captured")
        handle_razorpay_webhook(body, razorpay_sig(body), "evt_a")
        assert handle_razorpay_webhook(body, razorpay_sig(body), "evt_a") == "duplicate"

    def test_bad_signature_is_rejected(self, rz_pending):
        body = razorpay_body("payment.captured")
        with pytest.raises(ValidationError, match="signature"):
            handle_razorpay_webhook(body, razorpay_sig(body, "wrong"), "evt_a")
        with pytest.raises(ValidationError):
            handle_razorpay_webhook(body, "", "evt_a")

    def test_tampered_body_is_rejected(self, rz_pending):
        body = razorpay_body("payment.captured")
        tampered = razorpay_body("payment.captured", order_id="order_other")
        with pytest.raises(ValidationError):
            handle_razorpay_webhook(tampered, razorpay_sig(body), "evt_a")

    def test_missing_secret_fails_closed(self, rz_pending, settings):
        settings.RAZORPAY_WEBHOOK_SECRET = ""
        with pytest.raises(ValidationError, match="not configured"):
            handle_razorpay_webhook(b"{}", "x", "e")

    def test_failed_event_does_not_downgrade_a_captured_payment(self, rz_pending):
        _, payment = rz_pending
        body = razorpay_body("payment.captured")
        handle_razorpay_webhook(body, razorpay_sig(body), "evt_a")
        failed = razorpay_body("payment.failed")
        handle_razorpay_webhook(failed, razorpay_sig(failed), "evt_b")
        payment.refresh_from_db()
        assert payment.status == Payment.Status.CAPTURED

    def test_order_paid_is_handled_like_captured(self, rz_pending):
        booking, _ = rz_pending
        body = razorpay_body("order.paid")
        handle_razorpay_webhook(body, razorpay_sig(body), "evt_o")
        booking.refresh_from_db()
        assert booking.status == Booking.Status.CONFIRMED


class TestLatePayments:
    """The customer pays after the five-minute lock already expired the booking."""

    def test_expired_booking_is_revived_when_the_slot_is_still_free(self, pending):
        booking, _, slot = pending
        Booking.objects.filter(id=booking.id).update(status="expired")
        deliver_stripe("evt_l", "checkout.session.completed", "cs_1")
        booking.refresh_from_db()
        slot.refresh_from_db()
        assert booking.status == Booking.Status.CONFIRMED
        assert slot.state == ParkingSlot.SlotState.RESERVED

    def test_customer_is_refunded_when_the_slot_was_taken_meanwhile(
        self, pending, django_capture_on_commit_callbacks
    ):
        booking, payment, slot = pending
        Booking.objects.filter(id=booking.id).update(status="expired")
        BookingFactory(
            slot=slot,
            status="confirmed",
            start_time=booking.start_time,
            end_time=booking.end_time,
        )
        with (
            mock.patch("stripe.Refund.create", return_value=SimpleNamespace(id="re_auto")),
            django_capture_on_commit_callbacks(execute=True),
        ):
            deliver_stripe("evt_l", "checkout.session.completed", "cs_1")
        booking.refresh_from_db()
        payment.refresh_from_db()
        assert booking.status == Booking.Status.EXPIRED
        assert payment.status == Payment.Status.REFUNDED
        refund = Refund.objects.get(payment=payment)
        assert refund.status == Refund.Status.SUCCEEDED
        assert "Automatic refund" in refund.reason

    def test_payment_for_a_cancelled_booking_is_refunded(
        self, pending, django_capture_on_commit_callbacks
    ):
        booking, payment, _ = pending
        Booking.objects.filter(id=booking.id).update(status="cancelled")
        with (
            mock.patch("stripe.Refund.create", return_value=SimpleNamespace(id="re_c")),
            django_capture_on_commit_callbacks(execute=True),
        ):
            deliver_stripe("evt_c", "checkout.session.completed", "cs_1")
        assert Payment.objects.get(id=payment.id).status == Payment.Status.REFUNDED
        assert Booking.objects.get(id=booking.id).status == Booking.Status.CANCELLED

    def test_failed_automatic_refund_leaves_an_audit_row(
        self, pending, django_capture_on_commit_callbacks
    ):
        booking, payment, _ = pending
        Booking.objects.filter(id=booking.id).update(status="cancelled")
        with (
            mock.patch("stripe.Refund.create", side_effect=RuntimeError("gateway down")),
            django_capture_on_commit_callbacks(execute=True),
        ):
            deliver_stripe("evt_c", "checkout.session.completed", "cs_1")
        refund = Refund.objects.get(payment=payment)
        assert refund.status == Refund.Status.FAILED
        assert Payment.objects.get(id=payment.id).status == Payment.Status.CAPTURED
