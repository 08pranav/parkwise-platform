from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.accounts.views import CustomTokenObtainPairView
from apps.admin_api import demo
from apps.bookings.models import Booking
from apps.payments.models import Payment, Refund
from apps.penalties.models import Penalty
from apps.societies.models import Society

from .factories import BookingFactory, SuperAdminFactory, UserFactory

pytestmark = pytest.mark.django_db

TOKEN = "demo-reset-token-for-tests"


@pytest.fixture
def demo_on(settings):
    settings.DEMO_MODE = True
    settings.DEMO_RESET_TOKEN = TOKEN


class TestSeed:
    def test_creates_three_societies_one_user_per_role_and_every_booking_state(self):
        result = demo.seed()
        assert result["seeded"] is True
        assert Society.objects.count() == 3
        assert {u.role for u in User.objects.all()} == {
            "user",
            "society_admin",
            "guard",
            "super_admin",
        }
        states = set(Booking.objects.values_list("status", flat=True))
        assert states >= {
            "completed",
            "cancelled",
            "expired",
            "no_show",
            "confirmed",
            "partially_refunded",
        }
        assert Refund.objects.filter(is_full_refund=True).exists()
        assert Penalty.objects.exists()

    def test_the_demo_resident_can_still_book_after_seeding(self):
        """The one-booking-at-a-time rule must not block the account used for the live flow."""
        from apps.bookings.services import _user_has_blocking_booking

        demo.seed()
        assert not _user_has_blocking_booking(User.objects.get(email="user@parkwise.demo"))

    def test_the_demo_resident_has_no_unpaid_penalty_blocking_new_bookings(self):
        demo.seed()
        resident = User.objects.get(email="user@parkwise.demo")
        assert not Penalty.objects.filter(user=resident, status="unpaid").exists()
        assert Penalty.objects.filter(status="unpaid").exists()  # still shown for someone

    def test_the_seeded_paid_booking_has_a_valid_qr(self):
        from utils.qr import decode_qr_token

        demo.seed()
        booking = Booking.objects.get(status="confirmed", user__email="user2@parkwise.demo")
        assert decode_qr_token(booking.qr_code_token)["booking_id"] == str(booking.id)
        assert Payment.objects.filter(booking=booking, status="captured").exists()

    def test_every_demo_account_logs_in(self, api):
        demo.seed()
        for email in ("user", "owner", "admin", "guard", "super"):
            response = api.post(
                "/api/v1/auth/login/",
                {"email": f"{email}@parkwise.demo", "password": demo.DEMO_PASSWORD},
                format="json",
            )
            assert response.status_code == 200, email

    def test_seeding_twice_does_not_duplicate(self):
        demo.seed()
        assert demo.seed()["seeded"] is False
        assert Society.objects.count() == 3

    def test_reset_wipes_visitor_data_and_reseeds(self):
        demo.seed()
        UserFactory(email="visitor@example.com")
        demo.seed(reset=True)
        assert not User.objects.filter(email="visitor@example.com").exists()
        assert Society.objects.count() == 3

    def test_demo_data_contains_no_real_looking_contact_details(self):
        demo.seed()
        assert all(
            e.endswith("@parkwise.demo") for e in User.objects.values_list("email", flat=True)
        )


class TestResetEndpoint:
    URL = "/api/v1/admin/reset-demo/"

    def test_hidden_when_demo_mode_is_off(self, api, settings):
        settings.DEMO_MODE = False
        settings.DEMO_RESET_TOKEN = TOKEN
        assert api.post(self.URL, HTTP_AUTHORIZATION=f"Bearer {TOKEN}").status_code == 404

    def test_hidden_when_no_token_is_configured(self, api, settings):
        settings.DEMO_MODE = True
        settings.DEMO_RESET_TOKEN = ""
        assert api.post(self.URL).status_code == 404

    @pytest.mark.parametrize("header", [None, "Bearer wrong", "Basic abc", "Bearer"])
    def test_rejects_missing_or_wrong_tokens(self, api, demo_on, header):
        kwargs = {"HTTP_AUTHORIZATION": header} if header else {}
        assert api.post(self.URL, **kwargs).status_code == 401
        assert not Society.objects.exists()

    def test_correct_token_wipes_and_reseeds(self, api, demo_on):
        UserFactory(email="visitor@example.com")
        response = api.post(self.URL, HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
        assert response.status_code == 200 and response.json()["seeded"] is True
        assert not User.objects.filter(email="visitor@example.com").exists()


class TestFastForward:
    URL = "/api/v1/admin/demo/fast-forward/"

    def test_moves_an_active_booking_into_overstay(self, auth_client, demo_on):
        now = timezone.now()
        booking = BookingFactory(
            status="active",
            start_time=now - timedelta(minutes=30),
            end_time=now + timedelta(minutes=90),
            actual_entry=now - timedelta(minutes=25),
        )
        response = auth_client(SuperAdminFactory()).post(
            self.URL, {"booking_id": str(booking.id), "minutes": 150}, format="json"
        )
        assert response.status_code == 200
        booking.refresh_from_db()
        assert booking.end_time < now
        assert booking.actual_entry < booking.start_time + timedelta(minutes=10)

    def test_only_super_admins_and_only_in_demo_mode(self, auth_client, demo_on, settings):
        booking = BookingFactory(status="active")
        body = {"booking_id": str(booking.id), "minutes": 10}
        assert auth_client(UserFactory()).post(self.URL, body, format="json").status_code == 403
        settings.DEMO_MODE = False
        assert (
            auth_client(SuperAdminFactory()).post(self.URL, body, format="json").status_code == 404
        )

    @pytest.mark.parametrize("minutes", [0, -5, 5000, "abc"])
    def test_rejects_unreasonable_shifts(self, auth_client, demo_on, minutes):
        booking = BookingFactory(status="active")
        response = auth_client(SuperAdminFactory()).post(
            self.URL, {"booking_id": str(booking.id), "minutes": minutes}, format="json"
        )
        assert response.status_code == 400


class TestRateLimiting:
    def test_login_is_throttled_per_client(self, api, monkeypatch):
        cache.clear()
        monkeypatch.setattr(CustomTokenObtainPairView, "throttle_classes", [ScopedRateThrottle])
        monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"auth": "3/minute"})
        UserFactory(email="t@example.com")
        codes = [
            api.post(
                "/api/v1/auth/login/", {"email": "t@example.com", "password": "bad"}, format="json"
            ).status_code
            for _ in range(5)
        ]
        assert codes[:3] == [401, 401, 401]
        assert codes[3:] == [429, 429]
        cache.clear()

    def test_scopes_are_configured_for_auth_booking_and_payment(self, settings):
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        assert {"auth", "booking", "payment"} <= set(rates)
