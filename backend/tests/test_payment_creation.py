from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
import razorpay
from rest_framework.exceptions import ValidationError

from apps.payments import services as pay
from apps.payments.models import Payment
from apps.penalties.models import Penalty

from .factories import BookingFactory, PaymentFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def keys(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_x"
    settings.RAZORPAY_KEY_ID = "rzp_test_x"
    settings.RAZORPAY_KEY_SECRET = "secret"
    settings.FRONTEND_BASE_URL = "https://app.example.test"


def stripe_session(**kw):
    defaults = {"id": "cs_new", "url": "https://checkout.test/x", "payment_intent": None}
    return SimpleNamespace(**{**defaults, **kw})


class TestConfiguration:
    def test_stripe_requires_a_key(self, settings):
        settings.STRIPE_SECRET_KEY = ""
        with pytest.raises(ValidationError, match="not configured"):
            pay._get_stripe_client()

    def test_razorpay_requires_both_keys(self, settings):
        settings.RAZORPAY_KEY_SECRET = ""
        with pytest.raises(ValidationError, match="not configured"):
            pay._get_razorpay_client()

    def test_amounts_convert_to_paise(self):
        assert pay._amount_in_smallest_unit(Decimal("60.50")) == 6050

    def test_the_configured_sub_path_is_kept_for_requests_from_the_configured_site(self, settings):
        settings.FRONTEND_BASE_URL = "https://site.example.test/user/"
        same_site = SimpleNamespace(headers={"Origin": "https://site.example.test"})
        other_site = SimpleNamespace(headers={"Origin": "https://other.test"})
        assert pay._resolve_frontend_base_url(same_site) == "https://site.example.test/user"
        assert pay._resolve_frontend_base_url(other_site) == "https://other.test"
        assert pay._resolve_frontend_base_url() == "https://site.example.test/user"

    def test_checkout_returns_to_the_hash_route_of_the_app(self, settings):
        settings.FRONTEND_BASE_URL = "https://site.example.test/user"
        booking = BookingFactory(status="pending_payment")
        with mock.patch("stripe.checkout.Session.create", return_value=stripe_session()) as create:
            pay.create_stripe_checkout_session(booking)
        kwargs = create.call_args.kwargs
        assert kwargs["success_url"] == (
            f"https://site.example.test/user/#/bookings/{booking.id}"
            "?checkout=success&session_id={CHECKOUT_SESSION_ID}"
        )
        assert kwargs["cancel_url"].endswith(f"/#/bookings/{booking.id}?checkout=cancelled")

    def test_frontend_url_prefers_the_request_origin(self):
        request = SimpleNamespace(headers={"Origin": "https://shop.test/path", "Referer": ""})
        assert pay._resolve_frontend_base_url(request) == "https://shop.test"
        assert pay._resolve_frontend_base_url() == "https://app.example.test"


class TestStripeCheckout:
    def test_creates_a_session_and_a_waiting_payment(self):
        booking = BookingFactory(status="pending_payment")
        with mock.patch("stripe.checkout.Session.create", return_value=stripe_session()) as create:
            payment, url, secret = pay.create_stripe_checkout_session(booking)
        assert payment.status == Payment.Status.CREATED and payment.amount == booking.amount
        assert payment.stripe_checkout_session_id == "cs_new"
        assert url == "https://checkout.test/x" and secret is None
        kwargs = create.call_args.kwargs
        assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 6000
        assert kwargs["metadata"]["booking_id"] == str(booking.id)
        assert "success_url" in kwargs

    def test_embedded_mode_has_no_redirect_urls(self):
        booking = BookingFactory(status="pending_payment")
        session = stripe_session(client_secret="cs_secret")
        with mock.patch("stripe.checkout.Session.create", return_value=session) as create:
            _, _, secret = pay.create_stripe_checkout_session(booking, embedded=True)
        assert secret == "cs_secret"
        assert create.call_args.kwargs["ui_mode"] == "embedded"
        assert "success_url" not in create.call_args.kwargs

    def test_penalty_checkout(self):
        booking = BookingFactory(status="completed")
        penalty = Penalty.objects.create(
            booking=booking, user=booking.user, overstay_minutes=30, amount=Decimal("12.00")
        )
        with mock.patch("stripe.checkout.Session.create", return_value=stripe_session()) as create:
            payment, _, _ = pay.create_stripe_penalty_checkout_session(penalty, embedded=True)
        assert payment.payment_type == Payment.PaymentType.PENALTY
        assert create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"] == 1200


class TestRazorpayOrders:
    def fake_client(self, order_id="order_9"):
        client = mock.MagicMock()
        client.order.create.return_value = {"id": order_id}
        return client

    def test_booking_order(self):
        booking = BookingFactory(status="pending_payment")
        client = self.fake_client()
        with mock.patch.object(pay.razorpay, "Client", return_value=client):
            payment, order_id = pay.create_razorpay_order(booking)
        assert order_id == "order_9" and payment.razorpay_order_id == "order_9"
        assert client.order.create.call_args.kwargs["data"]["amount"] == 6000

    def test_penalty_order(self):
        booking = BookingFactory(status="completed")
        penalty = Penalty.objects.create(
            booking=booking, user=booking.user, overstay_minutes=30, amount=Decimal("12.00")
        )
        with mock.patch.object(pay.razorpay, "Client", return_value=self.fake_client("order_p")):
            payment, order_id = pay.create_razorpay_penalty_order(penalty)
        assert payment.payment_type == Payment.PaymentType.PENALTY and order_id == "order_p"


class TestVerifyRazorpay:
    def setup_payment(self):
        booking = BookingFactory(status="pending_payment")
        return booking, PaymentFactory(
            booking=booking,
            provider="razorpay",
            stripe_checkout_session_id=None,
            razorpay_order_id="order_1",
        )

    def test_valid_signature_captures_and_confirms(self):
        booking, payment = self.setup_payment()
        client = mock.MagicMock()
        with mock.patch.object(pay.razorpay, "Client", return_value=client):
            pay.verify_razorpay_payment("order_1", "pay_1", "sig", user=booking.user)
        booking.refresh_from_db()
        payment.refresh_from_db()
        assert payment.status == Payment.Status.CAPTURED and booking.status == "confirmed"
        assert payment.razorpay_signature == "sig"

    def test_bad_signature_is_rejected_and_nothing_changes(self):
        booking, payment = self.setup_payment()
        client = mock.MagicMock()
        client.utility.verify_payment_signature.side_effect = (
            razorpay.errors.SignatureVerificationError("bad")
        )
        with mock.patch.object(pay.razorpay, "Client", return_value=client):
            with pytest.raises(ValidationError, match="Invalid Razorpay signature"):
                pay.verify_razorpay_payment("order_1", "pay_1", "sig")
        payment.refresh_from_db()
        assert payment.status == Payment.Status.CREATED

    def test_another_users_payment_cannot_be_verified(self):
        from .factories import UserFactory

        _, payment = self.setup_payment()
        with mock.patch.object(pay.razorpay, "Client", return_value=mock.MagicMock()):
            with pytest.raises(ValidationError, match="does not belong"):
                pay.verify_razorpay_payment("order_1", "pay_1", "sig", user=UserFactory())

    def test_unknown_order(self):
        with mock.patch.object(pay.razorpay, "Client", return_value=mock.MagicMock()):
            with pytest.raises(ValidationError, match="not found"):
                pay.verify_razorpay_payment("order_x", "pay_1", "sig")

    def test_verifying_twice_is_harmless(self):
        booking, payment = self.setup_payment()
        with mock.patch.object(pay.razorpay, "Client", return_value=mock.MagicMock()):
            pay.verify_razorpay_payment("order_1", "pay_1", "sig")
            pay.verify_razorpay_payment("order_1", "pay_1", "sig")
        booking.refresh_from_db()
        assert booking.status == "confirmed"


class TestSyncRazorpay:
    def test_polling_captures_a_paid_order(self):
        booking = BookingFactory(status="pending_payment")
        payment = PaymentFactory(
            booking=booking,
            provider="razorpay",
            stripe_checkout_session_id=None,
            razorpay_order_id="order_1",
        )
        client = mock.MagicMock()
        client.order.payments.return_value = {"items": [{"id": "pay_7", "status": "captured"}]}
        with mock.patch.object(pay.razorpay, "Client", return_value=client):
            assert pay.sync_razorpay_order_status("order_1") is True
        booking.refresh_from_db()
        payment.refresh_from_db()
        assert booking.status == "confirmed" and payment.razorpay_payment_id == "pay_7"

    def test_polling_an_unpaid_order_does_nothing(self):
        client = mock.MagicMock()
        client.order.payments.return_value = {"items": [{"id": "p", "status": "failed"}]}
        with mock.patch.object(pay.razorpay, "Client", return_value=client):
            assert pay.sync_razorpay_order_status("order_1") is False

    def test_gateway_errors_are_contained(self):
        client = mock.MagicMock()
        client.order.fetch.side_effect = RuntimeError("down")
        with mock.patch.object(pay.razorpay, "Client", return_value=client):
            assert pay.sync_razorpay_order_status("order_1") is False


class TestPenaltyPayment:
    def test_a_captured_penalty_payment_marks_the_penalty_paid(self):
        booking = BookingFactory(status="completed")
        penalty = Penalty.objects.create(
            booking=booking, user=booking.user, overstay_minutes=30, amount=Decimal("12.00")
        )
        payment = PaymentFactory(
            booking=None,
            penalty=penalty,
            payment_type="penalty",
            amount=Decimal("12.00"),
            stripe_checkout_session_id="cs_pen",
        )
        session = SimpleNamespace(payment_status="paid", currency="inr", payment_intent="pi_pen")
        with mock.patch("stripe.checkout.Session.retrieve", return_value=session):
            pay.verify_checkout_session("cs_pen", user=None)
        penalty.refresh_from_db()
        payment.refresh_from_db()
        assert penalty.status == Penalty.Status.PAID
        assert payment.status == Payment.Status.CAPTURED

    def test_another_users_stripe_session_cannot_be_verified(self):
        from .factories import UserFactory

        PaymentFactory(stripe_checkout_session_id="cs_other")
        session = SimpleNamespace(payment_status="paid", currency="inr", payment_intent="pi")
        with mock.patch("stripe.checkout.Session.retrieve", return_value=session):
            with pytest.raises(ValidationError, match="does not belong"):
                pay.verify_checkout_session("cs_other", user=UserFactory())

    def test_unknown_session(self):
        session = SimpleNamespace(payment_status="paid", currency="inr", payment_intent="pi")
        with mock.patch("stripe.checkout.Session.retrieve", return_value=session):
            with pytest.raises(ValidationError, match="not found"):
                pay.verify_checkout_session("cs_none")
