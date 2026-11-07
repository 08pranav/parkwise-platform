from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.models import User, Vehicle
from apps.bookings.models import Booking
from apps.payments.models import Payment
from apps.societies.models import ParkingSlot, SlotAvailabilityWindow, Society


class SocietyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Society

    name = factory.Sequence(lambda n: f"Society {n}")
    address = "1 Test Road"
    city = "Mumbai"
    state = "Maharashtra"
    pincode = "400001"
    contact_email = "office@example.com"
    contact_phone = "9000000000"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    phone = factory.Sequence(lambda n: f"9{n:09d}")
    full_name = factory.Sequence(lambda n: f"User {n}")
    role = User.Role.USER
    society = factory.SubFactory(SocietyFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "Passw0rd!x1")
        return model_class.objects.create_user(*args, password=password, **kwargs)


class GuardFactory(UserFactory):
    role = User.Role.GUARD
    can_scan_entry = True
    can_scan_exit = True


class SuperAdminFactory(UserFactory):
    role = User.Role.SUPER_ADMIN
    society = None


class VehicleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Vehicle

    user = factory.SubFactory(UserFactory)
    vehicle_type = Vehicle.VehicleType.CAR
    registration_no = factory.Sequence(lambda n: f"MH01AB{n:04d}")


class SlotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ParkingSlot

    society = factory.SubFactory(SocietyFactory)
    slot_number = factory.Sequence(lambda n: f"S-{n}")
    slot_type = ParkingSlot.SlotType.CAR
    hourly_rate = Decimal("30.00")
    ownership_type = ParkingSlot.OwnershipType.SOCIETY
    approval_status = ParkingSlot.ApprovalStatus.APPROVED


class WindowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SlotAvailabilityWindow

    slot = factory.SubFactory(SlotFactory)
    day_of_week = 0
    start_time = "00:00"
    end_time = "23:59:59"


class BookingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Booking
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    vehicle = factory.LazyAttribute(lambda o: VehicleFactory(user=o.user))
    slot = factory.SubFactory(SlotFactory)
    booking_number = factory.Sequence(lambda n: f"BK-TEST-{n:06d}")
    start_time = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=10))
    end_time = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=2, minutes=10))
    status = Booking.Status.CONFIRMED
    amount = Decimal("60.00")
    base_amount = Decimal("60.00")
    qr_code_token = factory.Sequence(lambda n: f"placeholder-{n}")
    lock_expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=5))

    @factory.post_generation
    def real_qr(obj, create, extracted, **kwargs):
        if create:
            from utils.qr import generate_qr_token

            obj.qr_code_token = generate_qr_token(obj)
            obj.save(update_fields=["qr_code_token"])


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    booking = factory.SubFactory(BookingFactory)
    payment_type = Payment.PaymentType.BOOKING
    amount = Decimal("60.00")
    provider = Payment.Provider.STRIPE
    stripe_checkout_session_id = factory.Sequence(lambda n: f"cs_test_{n}")
    status = Payment.Status.CREATED
