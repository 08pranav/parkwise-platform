import hashlib
import hmac
import json
import logging
from decimal import Decimal
from urllib.parse import urlparse

import razorpay
import stripe
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.bookings.services import slot_is_available
from apps.bookings.state_machine import transition
from apps.societies.models import ParkingSlot

from .models import Payment, PaymentEvent, Refund

logger = logging.getLogger(__name__)

MONEY_MULTIPLIER = Decimal("100")


def _get_stripe_client():
    if not settings.STRIPE_SECRET_KEY:
        raise ValidationError("Stripe is not configured.")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _create_stripe_session(stripe_client, session_params):
    """Create a Checkout Session, turning Stripe's own rejections into a clean 400.

    Stripe refuses very small charges (about 50 US cents, roughly INR 43). Without this the
    caller would get a bare 500 for a short, cheap booking.
    """
    try:
        return stripe_client.checkout.Session.create(**session_params)
    except stripe.InvalidRequestError as exc:
        logger.warning("Stripe rejected the checkout session: %s", exc.user_message or exc)
        raise ValidationError(
            "Stripe cannot process this amount. Try a longer booking or pay with Razorpay."
        ) from exc
    except stripe.StripeError as exc:
        logger.exception("Stripe checkout session could not be created")
        raise ValidationError("Payment provider is unavailable. Please try again.") from exc


def sync_razorpay_order_status(razorpay_order_id):
    """Poll Razorpay for an order and capture the local payment if it was paid.

    Fallback for when the client callback and the webhook both failed to arrive.
    """
    client = _get_razorpay_client()
    try:
        client.order.fetch(razorpay_order_id)
        items = (client.order.payments(razorpay_order_id) or {}).get("items") or []
        captured = next((p for p in items if p["status"] == "captured"), None)
        if captured is None:
            return False
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(razorpay_order_id=razorpay_order_id)
            _capture_payment(payment, razorpay_payment_id=captured["id"])
        return True
    except Exception:
        logger.exception("Could not sync Razorpay order %s", razorpay_order_id)
        return False


def _get_razorpay_client():
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise ValidationError("Razorpay is not configured.")

    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def _origin(url):
    parsed = urlparse(url or "")
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None


def _resolve_frontend_base_url(request=None):
    """Where to send the browser after checkout.

    The web apps are served under a sub-path (``/user``), so when the request comes from the
    configured site the full configured URL is used; any other origin keeps just its origin.
    """
    configured = (settings.FRONTEND_BASE_URL or "").rstrip("/")
    configured_origin = _origin(configured)

    if request is not None:
        for header in ("Origin", "Referer"):
            origin = _origin(request.headers.get(header))
            if origin:
                return configured if origin == configured_origin else origin

    return configured if configured_origin else "http://127.0.0.1:3000"


def _booking_return_url(base_url, booking_id, query):
    # The Flutter web apps use hash routing: <site>/user/#/bookings/<id>
    return f"{base_url}/#/bookings/{booking_id}?{query}"


def _amount_in_smallest_unit(amount):
    return int((Decimal(amount) * MONEY_MULTIPLIER).quantize(Decimal("1")))


def _payment_intent_id(payment_intent):
    if isinstance(payment_intent, str):
        return payment_intent
    if isinstance(payment_intent, dict):
        return payment_intent.get("id")
    return getattr(payment_intent, "id", None)


SETTLED_STATUSES = (
    Payment.Status.CAPTURED,
    Payment.Status.REFUNDED,
    Payment.Status.PARTIALLY_REFUNDED,
)


def _capture_payment(payment, **fields):
    """Mark ``payment`` captured and apply its effects. Safe to call any number of times.

    The caller holds a row lock on ``payment``. A payment that is already settled
    is returned untouched, so duplicate webhooks, the client callback and the
    polling fallback can all arrive in any order.
    """
    if payment.status in SETTLED_STATUSES:
        return payment

    for name, value in fields.items():
        setattr(payment, name, value)
    payment.status = Payment.Status.CAPTURED
    payment.save(update_fields=["status", "updated_at", *fields])

    _mark_booking_as_confirmed(payment)
    _mark_penalty_as_paid(payment)
    return payment


def _mark_booking_as_confirmed(payment):
    """Confirm the booking a captured payment belongs to.

    * pending_payment -> confirmed, slot reserved.
    * expired, but the slot is still free for that window -> revived to confirmed.
    * expired/cancelled and the slot is gone -> the customer paid for nothing, so a
      full refund is issued once this transaction commits.
    """
    if not payment.booking_id:
        return payment

    booking = Booking.objects.select_for_update().get(id=payment.booking_id)
    if booking.status == Booking.Status.PENDING_PAYMENT:
        transition(booking, Booking.Status.CONFIRMED)
        _reserve_slot(booking)
    elif booking.status == Booking.Status.EXPIRED and _slot_still_free(booking):
        transition(booking, Booking.Status.CONFIRMED)
        _reserve_slot(booking)
    elif booking.status in (Booking.Status.EXPIRED, Booking.Status.CANCELLED):
        payment_id = payment.id
        transaction.on_commit(lambda: _auto_refund_late_payment(payment_id))

    return payment


def _reserve_slot(booking):
    slot = ParkingSlot.objects.select_for_update().get(id=booking.slot_id)
    slot.state = ParkingSlot.SlotState.RESERVED
    slot.save(update_fields=["state", "updated_at"])


def _slot_still_free(booking):
    slot = ParkingSlot.objects.select_related("society").get(id=booking.slot_id)
    return slot_is_available(
        slot, booking.vehicle.vehicle_type, booking.start_time, booking.end_time
    )


def _auto_refund_late_payment(payment_id):
    payment = Payment.objects.get(id=payment_id)
    try:
        issue_refund(
            payment,
            payment.amount,
            "Automatic refund: payment received after the booking could no longer be honoured.",
            update_booking=False,
        )
    except ValidationError:
        # The failed Refund row is the audit trail; a super admin can retry it.
        logger.exception("Automatic refund failed for payment %s", payment_id)


def _mark_penalty_as_paid(payment):
    if not payment.penalty_id:
        return payment

    penalty = payment.penalty
    if penalty and penalty.status == penalty.Status.UNPAID:
        penalty.status = penalty.Status.PAID
        penalty.save(update_fields=["status", "updated_at"])

    return payment


def create_stripe_checkout_session(booking, request=None, embedded=False):
    stripe_client = _get_stripe_client()
    frontend_base_url = _resolve_frontend_base_url(request)

    return_url = _booking_return_url(
        frontend_base_url, booking.id, "checkout=success&session_id={CHECKOUT_SESSION_ID}"
    )
    session_params = dict(
        client_reference_id=str(booking.id),
        customer_email=booking.user.email or None,
        mode="payment",
        metadata={
            "booking_id": str(booking.id),
            "booking_number": booking.booking_number,
        },
        payment_intent_data={
            "metadata": {
                "booking_id": str(booking.id),
                "booking_number": booking.booking_number,
            }
        },
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": "inr",
                    "unit_amount": _amount_in_smallest_unit(booking.amount),
                    "product_data": {
                        "name": f"Parking Booking {booking.booking_number}",
                        "description": (
                            f"Slot {booking.slot.slot_number} at {booking.slot.society.name}"
                        ),
                    },
                },
            }
        ],
    )

    if embedded:
        session_params.update(
            ui_mode="embedded",
            redirect_on_completion="never",
        )
    else:
        session_params.update(
            success_url=return_url,
            cancel_url=_booking_return_url(frontend_base_url, booking.id, "checkout=cancelled"),
        )

    checkout_session = _create_stripe_session(stripe_client, session_params)

    payment = Payment.objects.create(
        booking=booking,
        payment_type=Payment.PaymentType.BOOKING,
        amount=booking.amount,
        currency="INR",
        provider=Payment.Provider.STRIPE,
        stripe_checkout_session_id=checkout_session.id,
        stripe_payment_intent_id=_payment_intent_id(checkout_session.payment_intent),
    )

    return (
        payment,
        checkout_session.url,
        getattr(checkout_session, "client_secret", None),
    )


def create_razorpay_order(booking, request=None):
    client = _get_razorpay_client()

    order_params = {
        "amount": _amount_in_smallest_unit(booking.amount),
        "currency": "INR",
        "receipt": booking.booking_number,
        "notes": {
            "booking_id": str(booking.id),
            "booking_number": booking.booking_number,
            "user_email": booking.user.email,
        },
    }

    razorpay_order = client.order.create(data=order_params)

    payment = Payment.objects.create(
        booking=booking,
        payment_type=Payment.PaymentType.BOOKING,
        amount=booking.amount,
        currency="INR",
        provider=Payment.Provider.RAZORPAY,
        razorpay_order_id=razorpay_order["id"],
    )

    return payment, razorpay_order["id"]


def create_stripe_penalty_checkout_session(penalty, request=None, embedded=False):
    stripe_client = _get_stripe_client()
    frontend_base_url = _resolve_frontend_base_url(request)

    success_url = _booking_return_url(
        frontend_base_url,
        penalty.booking_id,
        "checkout=success&session_id={CHECKOUT_SESSION_ID}",
    )
    cancel_url = _booking_return_url(frontend_base_url, penalty.booking_id, "checkout=cancelled")

    session_params = dict(
        mode="payment",
        client_reference_id=str(penalty.id),
        customer_email=penalty.user.email or None,
        metadata={
            "penalty_id": str(penalty.id),
            "booking_id": str(penalty.booking_id),
        },
        payment_intent_data={
            "metadata": {
                "penalty_id": str(penalty.id),
                "booking_id": str(penalty.booking_id),
            }
        },
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": "inr",
                    "unit_amount": _amount_in_smallest_unit(penalty.amount),
                    "product_data": {
                        "name": f"Parking Penalty {penalty.id}",
                        "description": (f"Penalty for booking {penalty.booking.booking_number}"),
                    },
                },
            }
        ],
    )

    if embedded:
        session_params.update(
            ui_mode="embedded",
            redirect_on_completion="never",
        )
    else:
        session_params.update(
            success_url=success_url,
            cancel_url=cancel_url,
        )

    checkout_session = _create_stripe_session(stripe_client, session_params)

    payment = Payment.objects.create(
        penalty=penalty,
        payment_type=Payment.PaymentType.PENALTY,
        amount=penalty.amount,
        currency="INR",
        provider=Payment.Provider.STRIPE,
        stripe_checkout_session_id=checkout_session.id,
        stripe_payment_intent_id=_payment_intent_id(checkout_session.payment_intent),
    )

    return (
        payment,
        checkout_session.url,
        getattr(checkout_session, "client_secret", None),
    )


def create_razorpay_penalty_order(penalty, request=None):
    client = _get_razorpay_client()

    order_params = {
        "amount": _amount_in_smallest_unit(penalty.amount),
        "currency": "INR",
        "receipt": f"pen_{penalty.id}",
        "notes": {
            "penalty_id": str(penalty.id),
            "booking_id": str(penalty.booking_id),
            "user_email": penalty.user.email,
        },
    }

    razorpay_order = client.order.create(data=order_params)

    payment = Payment.objects.create(
        penalty=penalty,
        payment_type=Payment.PaymentType.PENALTY,
        amount=penalty.amount,
        currency="INR",
        provider=Payment.Provider.RAZORPAY,
        razorpay_order_id=razorpay_order["id"],
    )

    return payment, razorpay_order["id"]


def verify_checkout_session(checkout_session_id, user=None):
    stripe_client = _get_stripe_client()
    checkout_session = stripe_client.checkout.Session.retrieve(
        checkout_session_id,
        expand=["payment_intent"],
    )

    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(
                stripe_checkout_session_id=checkout_session_id
            )
        except Payment.DoesNotExist as exc:
            raise ValidationError("Payment not found.") from exc

        if user is not None and payment.booking and payment.booking.user_id != user.id:
            raise ValidationError("Payment does not belong to this user.")

        provider_fields = {
            "provider": Payment.Provider.STRIPE,
            "currency": (checkout_session.currency or payment.currency or "inr").upper(),
            "stripe_payment_intent_id": _payment_intent_id(checkout_session.payment_intent),
        }

        if checkout_session.payment_status != "paid":
            # Never downgrade a payment that is already settled.
            if payment.status == Payment.Status.CREATED:
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=["status", "updated_at"])
            raise ValidationError("Stripe checkout has not completed successfully.")

        return _capture_payment(payment, **provider_fields)


def verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature, user=None):
    client = _get_razorpay_client()

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError as exc:
        raise ValidationError("Invalid Razorpay signature.") from exc

    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(razorpay_order_id=razorpay_order_id)
        except Payment.DoesNotExist as exc:
            raise ValidationError("Payment not found for this order ID.") from exc

        if user is not None and payment.booking and payment.booking.user_id != user.id:
            raise ValidationError("Payment does not belong to this user.")

        return _capture_payment(
            payment,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )


def _record_event(provider, event_id, event_type, payload):
    """Store a webhook delivery. Returns False when this event was already processed."""
    _, created = PaymentEvent.objects.get_or_create(
        provider=provider,
        event_id=event_id,
        defaults={"event_type": event_type, "payload": payload},
    )
    return created


def handle_stripe_webhook(request_body, signature):
    """Verify and apply a Stripe webhook. Fails closed: no secret means no processing."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise ValidationError("Stripe webhook secret is not configured.")

    stripe_client = _get_stripe_client()
    try:
        event = stripe_client.Webhook.construct_event(
            payload=request_body,
            sig_header=signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise ValidationError("Invalid Stripe webhook signature.") from exc

    event_type = event.get("type")
    event_object = event.get("data", {}).get("object", {})

    # Recording and processing share one transaction: if processing fails, the
    # record rolls back and Stripe's retry is processed instead of skipped.
    with transaction.atomic():
        if not _record_event(Payment.Provider.STRIPE, event["id"], event_type, dict(event)):
            return "duplicate"

        if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            verify_checkout_session(event_object["id"])
        elif event_type == "payment_intent.payment_failed":
            _fail_payment(stripe_payment_intent_id=event_object.get("id"))
    return "processed"


def _fail_payment(**lookup):
    """Mark a payment failed only if it is still waiting; a captured payment is never downgraded."""
    if not all(lookup.values()):
        return
    payment = Payment.objects.select_for_update().filter(**lookup).first()
    if payment is not None and payment.status == Payment.Status.CREATED:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])


def handle_razorpay_webhook(request_body, signature, event_id):
    """Verify (HMAC-SHA256 over the raw body) and apply a Razorpay webhook."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        raise ValidationError("Razorpay webhook secret is not configured.")

    expected = hmac.new(secret.encode(), request_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        raise ValidationError("Invalid Razorpay webhook signature.")

    event = json.loads(request_body)
    event_type = event.get("event", "")
    entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    payment_id = entity.get("id")
    # Razorpay's event id header is the dedupe key; fall back to a content hash.
    event_id = event_id or hashlib.sha256(request_body).hexdigest()

    with transaction.atomic():
        if not _record_event(Payment.Provider.RAZORPAY, event_id, event_type, event):
            return "duplicate"

        if event_type in ("payment.captured", "order.paid") and order_id:
            payment = Payment.objects.select_for_update().filter(razorpay_order_id=order_id).first()
            if payment is not None:
                _capture_payment(payment, razorpay_payment_id=payment_id)
        elif event_type == "payment.failed" and order_id:
            _fail_payment(razorpay_order_id=order_id)
    return "processed"


def serialize_stripe_event(request_body):
    return json.loads(request_body)


def _begin_refund(payment_id, amount, reason, initiated_by, booking):
    """Validate and reserve the refund amount. Returns a ``pending`` Refund row.

    The payment row is locked, and pending refunds count against what is left to
    refund, so two concurrent requests cannot both refund the same money.
    """
    amount = Decimal(str(amount))
    if amount <= Decimal("0"):
        raise ValidationError("Refund amount must be greater than zero.")

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment_id)
        if payment.status not in SETTLED_STATUSES or payment.status == Payment.Status.REFUNDED:
            raise ValidationError("This payment cannot be refunded.")

        already = payment.refunds.exclude(status=Refund.Status.FAILED).aggregate(
            total=models.Sum("refund_amount")
        )["total"] or Decimal("0")
        remaining = payment.amount - already
        if amount > remaining:
            raise ValidationError(
                f"Refund amount (₹{amount}) exceeds the refundable balance (₹{remaining})."
            )

        return Refund.objects.create(
            payment=payment,
            booking=booking,
            initiated_by=initiated_by,
            refund_amount=amount,
            reason=reason,
            status=Refund.Status.PENDING,
            is_full_refund=amount == remaining and already == Decimal("0"),
        )


def _call_provider_refund(refund, initiated_by):
    payment = refund.payment
    booking = refund.booking
    meta = {
        "booking_id": str(booking.id) if booking else "",
        "booking_number": booking.booking_number if booking else "",
        "refund_id": str(refund.id),
        "reason": refund.reason[:200],
    }
    if initiated_by is not None:
        meta["admin_user"] = str(initiated_by.id)

    if payment.provider == Payment.Provider.STRIPE:
        if not payment.stripe_payment_intent_id:
            raise ValidationError("Stripe payment intent ID is missing - cannot process refund.")
        result = _get_stripe_client().Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            amount=_amount_in_smallest_unit(refund.refund_amount),
            reason="requested_by_customer",
            metadata=meta,
            idempotency_key=f"refund-{refund.id}",
        )
        return result.id
    if payment.provider == Payment.Provider.RAZORPAY:
        if not payment.razorpay_payment_id:
            raise ValidationError("Razorpay payment ID is missing - cannot process refund.")
        result = _get_razorpay_client().payment.refund(
            payment.razorpay_payment_id,
            {"amount": _amount_in_smallest_unit(refund.refund_amount), "notes": meta},
        )
        return result.get("id", "")
    raise ValidationError(f"Unknown payment provider '{payment.provider}'.")


def issue_refund(payment, amount, reason, initiated_by=None, booking=None, update_booking=True):
    """Refund ``amount`` of ``payment``: reserve, call the gateway, then settle.

    Every attempt leaves a ``Refund`` row (pending -> succeeded | failed), so a
    gateway error is never lost and a half-finished refund is visible to admins.
    """
    booking = booking or payment.booking
    refund = _begin_refund(payment.id, amount, reason, initiated_by, booking)

    try:
        provider_refund_id = _call_provider_refund(refund, initiated_by)
    except Exception as exc:
        refund.status = Refund.Status.FAILED
        refund.reason = f"{refund.reason} [gateway error: {str(exc)[:150]}]"
        refund.save(update_fields=["status", "reason", "updated_at"])
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError("The payment provider rejected the refund.") from exc

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(id=payment.id)
        refund.status = Refund.Status.SUCCEEDED
        refund.provider_refund_id = provider_refund_id
        refund.save(update_fields=["status", "provider_refund_id", "updated_at"])

        refunded = payment.refunds.filter(status=Refund.Status.SUCCEEDED).aggregate(
            total=models.Sum("refund_amount")
        )["total"]
        fully = refunded >= payment.amount
        payment.status = Payment.Status.REFUNDED if fully else Payment.Status.PARTIALLY_REFUNDED
        payment.save(update_fields=["status", "updated_at"])
        refund.is_full_refund = fully
        refund.save(update_fields=["is_full_refund", "updated_at"])

        if update_booking and booking is not None:
            _apply_refund_to_booking(booking.id, fully)

    return refund


def _apply_refund_to_booking(booking_id, fully_refunded):
    booking = Booking.objects.select_for_update().get(id=booking_id)
    target = Booking.Status.CANCELLED if fully_refunded else Booking.Status.PARTIALLY_REFUNDED
    if booking.status != target:
        transition(booking, target)

    # Release the slot on a full refund, or when the driver has not arrived yet.
    before_start = booking.start_time is not None and timezone.now() < booking.start_time
    if (fully_refunded or before_start) and booking.slot_id:
        slot = ParkingSlot.objects.select_for_update().get(id=booking.slot_id)
        if slot.state in (ParkingSlot.SlotState.RESERVED, ParkingSlot.SlotState.OCCUPIED):
            slot.state = ParkingSlot.SlotState.AVAILABLE
            slot.save(update_fields=["state", "updated_at"])


def process_refund(booking_id, refund_amount, reason, admin_user):
    """Super-admin refund (partial or full) for a booking's captured payment."""
    try:
        booking = Booking.objects.select_related("slot").get(id=booking_id)
    except Booking.DoesNotExist as exc:
        raise ValidationError("Booking not found.") from exc

    payment = (
        Payment.objects.filter(
            booking=booking,
            status__in=[Payment.Status.CAPTURED, Payment.Status.PARTIALLY_REFUNDED],
        )
        .order_by("-created_at")
        .first()
    )
    if payment is None:
        raise ValidationError("No captured payment found for this booking. Refund is not possible.")

    return issue_refund(payment, refund_amount, reason, initiated_by=admin_user, booking=booking)
