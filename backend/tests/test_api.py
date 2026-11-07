from datetime import timedelta

import pytest
from django.utils import timezone

from .factories import (
    BookingFactory,
    GuardFactory,
    SlotFactory,
    SocietyFactory,
    SuperAdminFactory,
    UserFactory,
    VehicleFactory,
)

pytestmark = pytest.mark.django_db


class TestAuthentication:
    def test_register_then_login_returns_tokens(self, api):
        society = SocietyFactory()
        response = api.post(
            "/api/v1/auth/register/",
            {
                "email": "new@example.com",
                "password": "Passw0rd!x1",
                "full_name": "New Person",
                "phone": "9876543210",
                "role": "user",
                "society_join_code": society.join_code,
                "flat_number": "A-1",
                "floor_number": "1",
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        login = api.post(
            "/api/v1/auth/login/",
            {"email": "new@example.com", "password": "Passw0rd!x1"},
            format="json",
        )
        assert login.status_code == 200
        assert "access" in login.json()

    def test_wrong_password_is_rejected(self, api):
        UserFactory(email="a@example.com")
        response = api.post(
            "/api/v1/auth/login/", {"email": "a@example.com", "password": "nope"}, format="json"
        )
        assert response.status_code == 401

    def test_protected_routes_need_a_token(self, api):
        for path in ("/api/v1/bookings/list/", "/api/v1/auth/profile/", "/api/v1/penalties/"):
            assert api.get(path).status_code == 401


class TestRolePermissions:
    def test_only_super_admins_can_use_refund_endpoints(self, auth_client):
        for actor in (UserFactory(), GuardFactory()):
            assert auth_client(actor).get("/api/v1/admin/refunds/lookup/?q=x").status_code == 403
        admin_response = auth_client(SuperAdminFactory()).get("/api/v1/admin/refunds/lookup/?q=x")
        assert admin_response.status_code != 403

    def test_residents_cannot_open_the_society_admin_dashboard(self, auth_client):
        assert auth_client(UserFactory()).get("/api/v1/admin/society/dashboard/").status_code == 403

    def test_a_guard_without_scan_rights_cannot_scan(self, auth_client):
        guard = GuardFactory(can_scan_entry=False, can_scan_exit=False)
        client = auth_client(guard)
        assert client.post("/api/v1/qr/entry/", {"qr_token": "x"}, format="json").status_code == 403
        assert client.post("/api/v1/qr/exit/", {"qr_token": "x"}, format="json").status_code == 403

    def test_residents_cannot_scan(self, auth_client):
        response = auth_client(UserFactory()).post(
            "/api/v1/qr/entry/", {"qr_token": "x"}, format="json"
        )
        assert response.status_code == 403

    def test_users_only_see_their_own_bookings(self, auth_client):
        mine = BookingFactory()
        BookingFactory()
        response = auth_client(mine.user).get("/api/v1/bookings/list/")
        assert response.status_code == 200
        ids = [b["id"] for b in response.json()["results"]]
        assert ids == [str(mine.id)]

    def test_users_cannot_read_someone_elses_booking(self, auth_client):
        other = BookingFactory()
        assert auth_client(UserFactory()).get(f"/api/v1/bookings/{other.id}/").status_code == 404


class TestBookingApi:
    def test_booking_and_error_shape(self, auth_client):
        society = SocietyFactory()
        user = UserFactory(society=society)
        vehicle = VehicleFactory(user=user)
        slot = SlotFactory(society=society)
        start = timezone.now() + timedelta(minutes=15)
        payload = {
            "slot_id": str(slot.id),
            "vehicle_id": str(vehicle.id),
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(hours=2)).isoformat(),
        }
        client = auth_client(user)
        created = client.post("/api/v1/bookings/", payload, format="json")
        assert created.status_code == 201, created.content
        assert created.json()["status"] == "pending_payment"

        second_user = UserFactory(society=society)
        payload["vehicle_id"] = str(VehicleFactory(user=second_user).id)
        clash = auth_client(second_user).post("/api/v1/bookings/", payload, format="json")
        assert clash.status_code == 400

    def test_cannot_book_with_someone_elses_vehicle(self, auth_client):
        society = SocietyFactory()
        user = UserFactory(society=society)
        slot = SlotFactory(society=society)
        start = timezone.now() + timedelta(minutes=15)
        response = auth_client(user).post(
            "/api/v1/bookings/",
            {
                "slot_id": str(slot.id),
                "vehicle_id": str(VehicleFactory().id),
                "start_time": start.isoformat(),
                "end_time": (start + timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        assert response.status_code == 400


class TestQrToken:
    def test_owner_can_read_the_token_of_a_paid_booking(self, auth_client):
        booking = BookingFactory(status="confirmed")
        response = auth_client(booking.user).get(f"/api/v1/bookings/{booking.id}/qr-token/")
        assert response.status_code == 200
        assert response.json()["qr_token"] == booking.qr_code_token

    def test_nobody_else_can_read_it(self, auth_client):
        booking = BookingFactory(status="confirmed")
        for actor in (UserFactory(), GuardFactory(society=booking.slot.society)):
            response = auth_client(actor).get(f"/api/v1/bookings/{booking.id}/qr-token/")
            assert response.status_code == 404

    @pytest.mark.parametrize("state", ["pending_payment", "cancelled", "expired", "completed"])
    def test_not_available_before_payment_or_after_the_stay(self, auth_client, state):
        booking = BookingFactory(status=state)
        response = auth_client(booking.user).get(f"/api/v1/bookings/{booking.id}/qr-token/")
        assert response.status_code == 400


class TestWebhookEndpoints:
    def test_unsigned_stripe_webhook_is_rejected(self, api, settings):
        settings.STRIPE_SECRET_KEY = "sk_test_x"
        settings.STRIPE_WEBHOOK_SECRET = "whsec_x"
        response = api.post("/api/v1/payments/webhook/", "{}", content_type="application/json")
        assert response.status_code == 400

    def test_unsigned_razorpay_webhook_is_rejected(self, api, settings):
        settings.RAZORPAY_WEBHOOK_SECRET = "s"
        response = api.post(
            "/api/v1/payments/razorpay/webhook/", "{}", content_type="application/json"
        )
        assert response.status_code == 400


class TestHealth:
    def test_reports_database_and_redis(self, api):
        response = api.get("/api/health/")
        assert response.status_code == 200
        body = response.json()
        assert body["database"] is True
        assert body["status"] in {"ok", "degraded"}

    def test_degraded_when_only_redis_is_down(self, api):
        from unittest import mock

        with mock.patch("parking_platform.health._check_redis", return_value=False):
            response = api.get("/api/health/")
        assert response.status_code == 200 and response.json()["status"] == "degraded"

    def test_unavailable_when_the_database_is_down(self, api):
        from unittest import mock

        with mock.patch("parking_platform.health._check_database", return_value=False):
            response = api.get("/api/health/")
        assert response.status_code == 503
