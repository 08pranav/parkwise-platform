"""Demo dataset for the public deployment.

Everything here is fictional: society names, people, phone numbers and vehicle
registrations are invented. Nothing is copied from real users.
"""

import random
import string
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, UserNotification, Vehicle
from apps.bookings.models import Booking
from apps.payments.models import Payment, PaymentEvent, Refund
from apps.penalties.models import Penalty
from apps.qr_validation.models import ScanEvent
from apps.societies.models import ParkingSlot, SlotAvailabilityWindow, Society
from utils.qr import generate_qr_token

DEMO_PASSWORD = "Demo@12345"
S = Booking.Status

SOCIETIES = [
    {
        "name": "Sea Breeze Residency",
        "address": "Hill Road, Bandra West",
        "city": "Mumbai",
        "pincode": "400050",
        "lat": "19.059600",
        "lng": "72.829500",
        "slots": {
            "car": [("A-01", 40), ("A-02", 40), ("A-03", 50), ("A-04", 50)],
            "bike": [("B-01", 15), ("B-02", 15)],
        },
    },
    {
        "name": "Lakeview Heights",
        "address": "Hiranandani Gardens, Powai",
        "city": "Mumbai",
        "pincode": "400076",
        "lat": "19.117600",
        "lng": "72.906000",
        "slots": {
            "car": [("P-01", 60), ("P-02", 60), ("P-03", 60), ("P-04", 70)],
            "bike": [("PB-01", 20)],
        },
    },
    {
        "name": "Harbour View Towers",
        "address": "Colaba Causeway, Colaba",
        "city": "Mumbai",
        "pincode": "400005",
        "lat": "18.906700",
        "lng": "72.814700",
        "slots": {
            "car": [("C-01", 80), ("C-02", 80), ("C-03", 90)],
            "bike": [("CB-01", 25), ("CB-02", 25)],
        },
    },
]


def _booking_number():
    tail = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{timezone.now():%Y%m%d}-{tail}"


def wipe():
    """Delete every row of the application's own data (the whole database is demo data)."""
    for model in (
        ScanEvent,
        Refund,
        PaymentEvent,
        Payment,
        Penalty,
        Booking,
        UserNotification,
        SlotAvailabilityWindow,
        ParkingSlot,
        Vehicle,
        User,
        Society,
    ):
        model.objects.all().delete()


def _user(email, name, phone, role=User.Role.USER, society=None, **extra):
    return User.objects.create_user(
        email=email,
        password=DEMO_PASSWORD,
        full_name=name,
        phone=phone,
        role=role,
        society=society,
        approval_status=User.ApprovalStatus.APPROVED,
        **extra,
    )


def _booking(user, vehicle, slot, start, end, status, *, rate=None, multiplier="1.00", **extra):
    hours = max(1, int(-(-(end - start).total_seconds() // 3600)))
    base = (rate or slot.hourly_rate) * hours
    mult = Decimal(multiplier)
    amount = (base * mult).quantize(Decimal("0.01"))
    booking = Booking.objects.create(
        booking_number=_booking_number(),
        user=user,
        vehicle=vehicle,
        slot=slot,
        start_time=start,
        end_time=end,
        status=status,
        base_amount=base,
        surge_multiplier=mult,
        surge_amount=amount - base,
        amount=amount,
        qr_code_token=_booking_number(),
        **extra,
    )
    booking.qr_code_token = generate_qr_token(booking)
    booking.save(update_fields=["qr_code_token"])
    return booking


def _payment(booking, status=Payment.Status.CAPTURED, provider=Payment.Provider.STRIPE):
    n = booking.booking_number[-6:].lower()
    fields = (
        {"stripe_checkout_session_id": f"cs_demo_{n}", "stripe_payment_intent_id": f"pi_demo_{n}"}
        if provider == Payment.Provider.STRIPE
        else {"razorpay_order_id": f"order_demo_{n}", "razorpay_payment_id": f"pay_demo_{n}"}
    )
    return Payment.objects.create(
        booking=booking,
        payment_type=Payment.PaymentType.BOOKING,
        amount=booking.amount,
        provider=provider,
        status=status,
        **fields,
    )


@transaction.atomic
def seed(*, reset=False):
    if reset:
        wipe()
    elif Society.objects.exists():
        return {"seeded": False, "reason": "data already present (use --reset)"}

    now = timezone.now()
    societies = []
    for spec in SOCIETIES:
        society = Society.objects.create(
            name=spec["name"],
            address=spec["address"],
            city=spec["city"],
            state="Maharashtra",
            pincode=spec["pincode"],
            latitude=Decimal(spec["lat"]),
            longitude=Decimal(spec["lng"]),
            contact_email=f"office@{spec['name'].split()[0].lower()}.parkwise.demo",
            contact_phone="9000000000",
        )
        societies.append(society)
        for slot_type, slots in spec["slots"].items():
            for number, rate in slots:
                slot = ParkingSlot.objects.create(
                    society=society,
                    slot_number=number,
                    slot_type=slot_type,
                    hourly_rate=Decimal(rate),
                    floor="B1" if slot_type == "car" else "G",
                )
                # Society slots with a window are only open during it; others are open all day.
                if number.endswith(("-04", "-03")) and slot_type == "car":
                    for day in range(7):
                        SlotAvailabilityWindow.objects.create(
                            slot=slot, day_of_week=day, start_time="06:00", end_time="23:59:59"
                        )

    bandra, powai, colaba = societies

    # --- people (one per role, plus supporting accounts) -------------------------------
    super_admin = _user("super@parkwise.demo", "Super Admin", "9000000001", User.Role.SUPER_ADMIN)
    admin = _user(
        "admin@parkwise.demo", "Meera Kulkarni", "9000000002", User.Role.SOCIETY_ADMIN, bandra
    )
    _user(
        "admin.powai@parkwise.demo", "Rohan Deshpande", "9000000003", User.Role.SOCIETY_ADMIN, powai
    )
    _user(
        "admin.colaba@parkwise.demo", "Farah Sheikh", "9000000004", User.Role.SOCIETY_ADMIN, colaba
    )
    guard = _user(
        "guard@parkwise.demo",
        "Ramesh Patil",
        "9000000005",
        User.Role.GUARD,
        bandra,
        can_scan_entry=True,
        can_scan_exit=True,
    )
    owner = _user(
        "owner@parkwise.demo",
        "Anil Mehta",
        "9000000006",
        society=bandra,
        flat_number="B-402",
        floor_number="4",
    )
    resident = _user(
        "user@parkwise.demo",
        "Priya Nair",
        "9000000007",
        society=bandra,
        flat_number="A-101",
        floor_number="1",
    )
    second = _user(
        "user2@parkwise.demo",
        "Karan Shah",
        "9000000008",
        society=bandra,
        flat_number="A-203",
        floor_number="2",
    )
    third = _user(
        "user3@parkwise.demo",
        "Sneha Iyer",
        "9000000009",
        society=powai,
        flat_number="C-12",
        floor_number="1",
    )

    car = Vehicle.objects.create(
        user=resident, vehicle_type="car", registration_no="MH01DM1001", make_model="Hyundai i20"
    )
    bike = Vehicle.objects.create(
        user=resident, vehicle_type="bike", registration_no="MH01DM1002", make_model="Honda Activa"
    )
    car2 = Vehicle.objects.create(
        user=second, vehicle_type="car", registration_no="MH01DM2001", make_model="Maruti Swift"
    )
    car3 = Vehicle.objects.create(
        user=third, vehicle_type="car", registration_no="MH01DM3001", make_model="Tata Nexon"
    )
    Vehicle.objects.create(
        user=owner, vehicle_type="car", registration_no="MH01DM4001", make_model="Honda City"
    )

    # --- a resident-owned slot waiting for approval and an approved one ----------------
    approved_owner_slot = ParkingSlot.objects.create(
        society=bandra,
        slot_number="R-402",
        slot_type="car",
        hourly_rate=Decimal("35"),
        ownership_type="resident",
        owner=owner,
        created_by=owner,
        approval_status="approved",
        approved_by=admin,
        approved_at=now - timedelta(days=3),
        floor="B1",
    )
    pending_owner_slot = ParkingSlot.objects.create(
        society=bandra,
        slot_number="R-403",
        slot_type="bike",
        hourly_rate=Decimal("12"),
        ownership_type="resident",
        owner=owner,
        created_by=owner,
        approval_status="pending",
        state="blocked",
        floor="G",
    )
    for slot in (approved_owner_slot, pending_owner_slot):
        for day in range(7):
            SlotAvailabilityWindow.objects.create(
                slot=slot, day_of_week=day, start_time="08:00", end_time="20:00"
            )

    car_slots = list(
        ParkingSlot.objects.filter(
            society=bandra, slot_type="car", ownership_type="society"
        ).order_by("slot_number")
    )
    bike_slot = ParkingSlot.objects.filter(
        society=bandra, slot_type="bike", ownership_type="society"
    ).first()

    # --- history for the demo resident: one booking in every state ---------------------
    day = timedelta(days=1)
    h = timedelta(hours=1)
    completed = _booking(
        resident,
        car,
        car_slots[0],
        now - 3 * day,
        now - 3 * day + 3 * h,
        S.COMPLETED,
        actual_entry=now - 3 * day + timedelta(minutes=4),
        actual_exit=now - 3 * day + 2 * h + timedelta(minutes=50),
    )
    _payment(completed)

    overstayed = _booking(
        second,
        car2,
        car_slots[1],
        now - 2 * day,
        now - 2 * day + 2 * h,
        S.COMPLETED,
        actual_entry=now - 2 * day + timedelta(minutes=2),
        actual_exit=now - 2 * day + 3 * h + timedelta(minutes=20),
    )
    _payment(overstayed, provider=Payment.Provider.RAZORPAY)
    Penalty.objects.create(
        booking=overstayed,
        user=second,
        overstay_minutes=80,
        amount=(overstayed.amount * Decimal("0.20") * 2).quantize(Decimal("0.01")),
    )

    refunded = _booking(
        resident, car, car_slots[2], now - 5 * day, now - 5 * day + 2 * h, S.CANCELLED
    )
    refunded_payment = _payment(refunded, status=Payment.Status.REFUNDED)
    Refund.objects.create(
        payment=refunded_payment,
        booking=refunded,
        initiated_by=super_admin,
        refund_amount=refunded.amount,
        reason="Duplicate booking, refunded in full",
        provider_refund_id="re_demo_full",
        status=Refund.Status.SUCCEEDED,
        is_full_refund=True,
    )

    partial = _booking(
        resident, bike, bike_slot, now - 6 * day, now - 6 * day + 2 * h, S.PARTIALLY_REFUNDED
    )
    partial_payment = _payment(partial, status=Payment.Status.PARTIALLY_REFUNDED)
    Refund.objects.create(
        payment=partial_payment,
        booking=partial,
        initiated_by=super_admin,
        refund_amount=(partial.amount / 2).quantize(Decimal("0.01")),
        reason="Goodwill partial refund",
        provider_refund_id="re_demo_part",
        status=Refund.Status.SUCCEEDED,
    )

    _booking(resident, car, car_slots[3], now - 4 * day, now - 4 * day + 2 * h, S.CANCELLED)
    _booking(resident, car, car_slots[0], now - 7 * day, now - 7 * day + 2 * h, S.EXPIRED)
    no_show = _booking(resident, car, car_slots[1], now - 8 * day, now - 8 * day + 2 * h, S.NO_SHOW)
    _payment(no_show)

    # --- a paid booking with a valid QR, ready for the guard to scan --------------------
    live = _booking(
        second, car2, car_slots[2], now - timedelta(minutes=5), now + 3 * h, S.CONFIRMED
    )
    _payment(live)
    car_slots[2].state = ParkingSlot.SlotState.RESERVED
    car_slots[2].save(update_fields=["state", "updated_at"])
    ScanEvent.objects.create(
        guard=guard, society=bandra, booking=completed, event_type="entry", result="approved"
    )
    ScanEvent.objects.create(
        guard=guard, society=bandra, booking=completed, event_type="exit", result="approved"
    )
    ScanEvent.objects.create(
        guard=guard,
        society=bandra,
        booking=None,
        event_type="entry",
        result="denied",
        error_message="Invalid QR code.",
    )

    # --- Powai is busy, so its quotes show surge pricing -------------------------------
    powai_slots = list(ParkingSlot.objects.filter(society=powai, slot_type="car"))
    for slot in powai_slots[:3]:
        busy = _booking(third, car3, slot, now + h, now + 5 * h, S.CONFIRMED)
        _payment(busy)

    # --- notifications -----------------------------------------------------------------
    UserNotification.objects.create(
        user=owner,
        notification_type="slot_approved",
        title="Slot approved",
        message="Your slot R-402 was approved by the society admin.",
        payload={"slot_id": str(approved_owner_slot.id)},
    )
    UserNotification.objects.create(
        user=admin,
        notification_type="slot_pending",
        title="New slot approval request",
        message="Anil Mehta submitted a new parking slot for approval.",
        payload={"slot_id": str(pending_owner_slot.id)},
    )
    UserNotification.objects.create(
        user=resident,
        notification_type="join_approved",
        title="Welcome to Sea Breeze Residency",
        message="Your society admin approved your membership.",
        payload={},
    )

    return {
        "seeded": True,
        "societies": Society.objects.count(),
        "users": User.objects.count(),
        "slots": ParkingSlot.objects.count(),
        "bookings": Booking.objects.count(),
    }
