# API reference

Generated from [`openapi.yaml`](openapi.yaml): **55 paths, 71 operations**.
Interactive docs are served by the API at `/api/docs/` (Swagger UI) and `/api/schema/`.

Authentication is JWT: `POST /api/v1/auth/login/` returns `access` and `refresh` tokens; send
`Authorization: Bearer <access>`. Errors are JSON, usually `{"error": "..."}` or a DRF validation body.
Login, registration, booking and payment endpoints are rate limited (HTTP 429 when exceeded).

Known gap: some views have no `serializer_class`, so their request and response bodies are not described
in the generated schema; the paths and methods below are complete.

## Accounts and authentication

| Method | Path | Operation |
|---|---|---|
| POST | `/api/v1/auth/guard/register/` | v1_auth_guard_register_create |
| GET | `/api/v1/auth/guards/` | v1_auth_guards_list |
| POST | `/api/v1/auth/guards/` | v1_auth_guards_create |
| GET | `/api/v1/auth/guards/{id}/` | v1_auth_guards_retrieve |
| PUT | `/api/v1/auth/guards/{id}/` | v1_auth_guards_update |
| PATCH | `/api/v1/auth/guards/{id}/` | v1_auth_guards_partial_update |
| DELETE | `/api/v1/auth/guards/{id}/` | v1_auth_guards_destroy |
| POST | `/api/v1/auth/login/` | v1_auth_login_create |
| GET | `/api/v1/auth/notifications/` | v1_auth_notifications_list |
| PUT | `/api/v1/auth/notifications/{id}/read/` | v1_auth_notifications_read_update |
| PATCH | `/api/v1/auth/notifications/{id}/read/` | v1_auth_notifications_read_partial_update |
| GET | `/api/v1/auth/profile/` | v1_auth_profile_retrieve |
| PUT | `/api/v1/auth/profile/` | v1_auth_profile_update |
| PATCH | `/api/v1/auth/profile/` | v1_auth_profile_partial_update |
| POST | `/api/v1/auth/register/` | v1_auth_register_create |
| POST | `/api/v1/auth/token/refresh/` | v1_auth_token_refresh_create |
| GET | `/api/v1/auth/vehicles/` | v1_auth_vehicles_list |
| POST | `/api/v1/auth/vehicles/` | v1_auth_vehicles_create |
| DELETE | `/api/v1/auth/vehicles/{id}/` | v1_auth_vehicles_destroy |

## Societies, slots and search

| Method | Path | Operation |
|---|---|---|
| GET | `/api/v1/societies/` | v1_societies_list |
| POST | `/api/v1/societies/` | v1_societies_create |
| GET | `/api/v1/societies/destinations/autocomplete/` | v1_societies_destinations_autocomplete_retrieve |
| GET | `/api/v1/societies/destinations/reverse-geocode/` | v1_societies_destinations_reverse_geocode_retrieve |
| GET | `/api/v1/societies/geocode/` | v1_societies_geocode_retrieve |
| GET | `/api/v1/societies/public/` | v1_societies_public_list |
| POST | `/api/v1/societies/search/` | v1_societies_search_create |
| GET | `/api/v1/societies/{id}/` | v1_societies_retrieve |
| PUT | `/api/v1/societies/{id}/` | v1_societies_update |
| PATCH | `/api/v1/societies/{id}/` | v1_societies_partial_update |
| GET | `/api/v1/societies/{society_id}/join-requests/` | v1_societies_join_requests_list |
| POST | `/api/v1/societies/{society_id}/join-requests/{id}/decision/` | v1_societies_join_requests_decision_create |
| GET | `/api/v1/societies/{society_id}/slots/` | v1_societies_slots_list |
| POST | `/api/v1/societies/{society_id}/slots/` | v1_societies_slots_create |
| GET | `/api/v1/societies/{society_id}/slots/{id}/` | v1_societies_slots_retrieve |
| PUT | `/api/v1/societies/{society_id}/slots/{id}/` | v1_societies_slots_update |
| PATCH | `/api/v1/societies/{society_id}/slots/{id}/` | v1_societies_slots_partial_update |
| GET | `/api/v1/societies/{society_id}/slots/{id}/availability/` | v1_societies_slots_availability_list |
| POST | `/api/v1/societies/{society_id}/slots/{id}/availability/` | v1_societies_slots_availability_create |
| POST | `/api/v1/societies/{society_id}/slots/{id}/block/` | v1_societies_slots_block_create |
| POST | `/api/v1/societies/{society_id}/slots/{id}/decision/` | v1_societies_slots_decision_create |
| POST | `/api/v1/societies/{society_id}/slots/{id}/toggle-active/` | v1_societies_slots_toggle_active_create |
| POST | `/api/v1/societies/{society_id}/slots/{id}/unblock/` | v1_societies_slots_unblock_create |

## Bookings

| Method | Path | Operation |
|---|---|---|
| POST | `/api/v1/bookings/` | v1_bookings_create |
| GET | `/api/v1/bookings/list/` | v1_bookings_list_list |
| GET | `/api/v1/bookings/{id}/` | v1_bookings_retrieve |
| POST | `/api/v1/bookings/{id}/cancel/` | v1_bookings_cancel_create |
| GET | `/api/v1/bookings/{id}/overtime/` | v1_bookings_overtime_retrieve |
| GET | `/api/v1/bookings/{id}/qr-token/` | v1_bookings_qr_token_retrieve |
| GET | `/api/v1/bookings/{id}/qr/` | v1_bookings_qr_retrieve |

## Payments and webhooks

| Method | Path | Operation |
|---|---|---|
| POST | `/api/v1/payments/initiate/` | v1_payments_initiate_create |
| POST | `/api/v1/payments/manual-verify/` | v1_payments_manual_verify_create |
| POST | `/api/v1/payments/razorpay/verify/` | v1_payments_razorpay_verify_create |
| POST | `/api/v1/payments/razorpay/webhook/` | v1_payments_razorpay_webhook_create |
| POST | `/api/v1/payments/verify/` | v1_payments_verify_create |
| POST | `/api/v1/payments/webhook/` | v1_payments_webhook_create |

## Gate scanning (QR)

| Method | Path | Operation |
|---|---|---|
| POST | `/api/v1/qr/entry/` | v1_qr_entry_create |
| POST | `/api/v1/qr/exit/` | v1_qr_exit_create |

## Penalties

| Method | Path | Operation |
|---|---|---|
| GET | `/api/v1/penalties/` | v1_penalties_list |
| POST | `/api/v1/penalties/{id}/pay/` | v1_penalties_pay_create |

## Admin, refunds and demo tools

| Method | Path | Operation |
|---|---|---|
| GET | `/api/v1/admin/dashboard/` | v1_admin_dashboard_retrieve |
| POST | `/api/v1/admin/demo/fast-forward/` | v1_admin_demo_fast_forward_create |
| GET | `/api/v1/admin/refunds/` | v1_admin_refunds_retrieve |
| POST | `/api/v1/admin/refunds/` | v1_admin_refunds_create |
| GET | `/api/v1/admin/refunds/lookup/` | v1_admin_refunds_lookup_retrieve |
| POST | `/api/v1/admin/reset-demo/` | v1_admin_reset_demo_create |
| GET | `/api/v1/admin/societies/{society_id}/stats/` | v1_admin_societies_stats_retrieve |
| GET | `/api/v1/admin/society/dashboard/` | v1_admin_society_dashboard_retrieve |
| GET | `/api/v1/admin/society/guards/` | v1_admin_society_guards_retrieve |
| POST | `/api/v1/admin/society/guards/{guard_id}/approve/` | v1_admin_society_guards_approve_create |
| POST | `/api/v1/admin/society/guards/{guard_id}/reject/` | v1_admin_society_guards_reject_create |

## Other

| Method | Path | Operation |
|---|---|---|
| GET | `/api/health/` | health_retrieve |
