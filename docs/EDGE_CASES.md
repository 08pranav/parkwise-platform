# Edge cases we solved

Every entry below is something the code handles today and a test proves. Test names refer to files in
[`backend/tests/`](../backend/tests). Where a case came from the project's history or was found while
testing the live deployment, the entry says so.

Run them all: `make infra && make test` (236 tests; `services.py` modules are covered at 96.6%).

## Booking and availability

### 1. Two people book the same slot at the same moment
- **Scenario:** eight residents press "Book" for the same slot and time within a few milliseconds.
- **Why it is hard:** each request checks "is the slot free?" and then inserts. Run in parallel, every request sees "free".
- **How we handle it:** `create_booking` takes a row lock on the slot (`select_for_update`) inside one transaction, so requests for that slot run one after another and the loser sees the winner's booking.
- **Proof:** `test_booking_concurrency.py` fires 8 threads at one slot and expects exactly one success. We also removed the lock to confirm the test fails without it (it failed 3 times out of 3).

### 2. A booking jumps to an impossible state
- **Scenario:** a late webhook, a double click or a retried task tries to move a `completed` booking back to `active`, or revive a `cancelled` one.
- **Why it is hard:** statuses were set directly in six different places.
- **How we handle it:** one transition table (`bookings/state_machine.py`); every change goes through `transition()`, which raises on an invalid move. `pending_payment → confirmed → active → completed`, with `expired`, `cancelled`, `no_show`, `partially_refunded` as the other states. `cancelled` is terminal.
- **Proof:** `test_state_machine.py` (allowed and forbidden moves, and that a refused move leaves the row untouched).

### 3. An unpaid booking holds a slot forever
- **Scenario:** a user opens checkout and walks away; or Redis is down so the expiry task never queues.
- **Why it is hard:** the slot is locked for 5 minutes, and a single scheduled task can be lost.
- **How we handle it:** two layers. A per-booking task fires after 5 minutes, queued after the transaction commits and without blocking the request. A sweep task runs every minute and expires anything past its lock. Both only touch rows still in `pending_payment`, under a row lock, so running them twice or together is harmless.
- **Proof:** `test_tasks.py` (expire once, never touch paid bookings, sweep idempotent, unknown ids ignored).

### 4. A driver books and never shows up
- **Scenario:** a confirmed booking passes its halfway point with no check-in.
- **How we handle it:** `detect_no_shows` (every 5 minutes) marks it `no_show` and frees the slot; the gate refuses entry after the same halfway point, so the two rules agree. A user can only hold one blocking booking until then.
- **Proof:** `test_tasks.py::test_no_show_*`, `test_qr_gate.py::test_entry_after_the_halfway_point_counts_as_no_show`, `test_booking_services.py::test_a_user_cannot_hold_two_blocking_bookings`.

### 5. Availability windows, time zones and midnight
- **Scenario:** a slot is open 20:00–23:59 on Monday and 00:00–06:00 on Tuesday, and someone books 22:00–02:00. Another request arrives as 04:30 UTC (which is 10:00 in India). Another starts at 00:30 IST Tuesday, which is still Monday in UTC.
- **Why it is hard:** windows are wall-clock times per weekday. Comparing naive `.time()` values or using the UTC weekday gives wrong answers, and a booking that crosses midnight needs two windows.
- **How we handle it:** datetimes are stored in UTC and converted to local time (IST) for window checks. The booking is split at local midnight and every slice must fit a window for its own day. A society slot with no window on a day is open all day; a resident slot with no window is closed. Windows end at most at 23:59:59, so end-of-day slices compare as 23:59:59 (this exact off-by-a-microsecond bug was caught by the first midnight test).
- **Proof:** `test_availability.py` (UTC input, weekday-follows-local-time, midnight crossing with and without the next day's window, resident slot with no window).
- **From history:** strict slot availability windows were added in commit `70ca329`; the 5-minute grace for clock drift in `3191759`, covered by `test_allows_five_minutes_of_clock_drift`.

## Pricing

### 6. Surge pricing must be fair and repeatable
- **Scenario:** a resident asks for a quote and then pays; the price must be the one quoted, and the same inputs must always give the same price.
- **How we handle it:** pricing is a set of pure `Decimal` functions (`bookings/pricing.py`). Own-society occupancy above 80% adds 0.50, above 50% adds 0.20; nearby societies (about 5 km) above 80% / 50% / 30% add 0.40 / 0.20 / 0.10. Thresholds are strict (exactly 50% is not surge), duration is billed in whole hours rounded up, money is rounded half-up to 2 places.
- **Proof:** `test_pricing.py` (every tier boundary, stacking to a maximum of 1.90, rounding), plus `test_booking_services.py` for own-society and nearby surge end to end. The earlier code mixed `float` and `Decimal`.

## Payments

### 7. A forged webhook
- **Scenario:** anyone can POST to a public webhook URL and claim a payment succeeded or failed.
- **How we handle it:** both endpoints verify the signature over the raw body (Stripe's `construct_event`; Razorpay HMAC-SHA256) and **fail closed**: with no secret configured they refuse to process anything. The previous Stripe handler parsed unsigned JSON when no secret was set and trusted `payment_intent.payment_failed` events.
- **Proof:** `test_payment_webhooks.py` (wrong secret, missing header, tampered body, no secret) and `test_api.py::TestWebhookEndpoints`.

### 8. The provider delivers the same event twice
- **How we handle it:** each accepted event is stored under a unique `(provider, event_id)` (`PaymentEvent`). A repeat returns "duplicate" and changes nothing. The record is written in the same transaction as the processing, so if processing fails the record rolls back and the provider's retry is processed instead of being skipped.
- **Proof:** `test_duplicate_delivery_is_ignored`, `test_failed_processing_rolls_back_the_event_so_the_retry_is_processed`.

### 9. Events arrive out of order
- **Scenario:** `payment_failed` arrives after `checkout.session.completed`, or before it.
- **How we handle it:** a failure only applies to a payment still waiting (`created`); a captured payment is never downgraded, and a failed one can still be captured by a later success.
- **Proof:** `test_payment_failed_never_downgrades_a_captured_payment`, `test_out_of_order_events_still_end_captured`, and the Razorpay equivalent.

### 10. The customer pays after the 5-minute lock expired
- **Scenario:** the card is charged at minute 6; the booking is already `expired`.
- **How we handle it:** if the slot is still free for that window the booking is revived to `confirmed`; if it was taken (or the booking was cancelled), the payment is refunded automatically after the transaction commits. A failed automatic refund leaves a `failed` refund row for a super admin to retry.
- **Proof:** `TestLatePayments` in `test_payment_webhooks.py` (4 tests).
- **Also fixed:** the Razorpay polling fallback used to set a booking to `confirmed` without reserving the slot; every path now shares one idempotent capture function.

### 11. Refunds: double spend, partial refunds and gateway failures
- **Scenario:** two admins click "Refund" together; or the gateway call fails after we decided to refund; or an admin refunds 40 now and 60 later.
- **How we handle it:** a refund first reserves its amount under a lock on the payment (pending refunds count against the balance), then calls the gateway with an idempotency key tied to the refund row, then settles payment, booking and slot in one transaction. A gateway error leaves a `failed` refund row (audit trail) and releases the amount. Partial refunds accumulate until the balance is zero.
- **Proof:** `test_refunds.py` (full, partial, accumulating, over-refund, zero, gateway failure leaves everything unchanged, retry after failure, idempotency key, Razorpay path, and a two-thread race that reaches the gateway exactly once).

## Gate (QR)

### 12. QR replay, forgery and wrong gate
- **Scenario:** someone scans the same QR twice, scans a screenshot of an old one, edits a token, or scans at another society's gate.
- **How we handle it:** the QR carries a signed token that must also equal the token stored on the booking. A booking admits one entry because entry requires `confirmed` and moves it to `active`; the second scan is refused ("Only confirmed bookings allow entry") and logged. Other societies, early arrivals, expired bookings and the no-show window are all refused. Every scan, approved or denied, is stored as a `ScanEvent`.
- **Proof:** `test_qr_gate.py` (replay, garbage and forged tokens, stale token, wrong society, unpaid, early, expired, no-show window, final states).

### 13. Overstay penalties
- **Scenario:** a driver leaves 20 seconds late; another leaves at 00:20 for a booking that ended at 23:50; a guard's app retries the exit scan.
- **How we handle it:** overstay is measured in aware datetimes, rounded **up** to whole minutes, and billed per started hour at 20% of the booking amount. The penalty is created in the same transaction as the exit, and the database enforces one penalty per booking, so a retry cannot double charge. Display time is IST; storage is UTC.
- **Proof:** `test_penalties.py` (UTC vs IST equal, across local midnight, rounding, DB constraint) and `test_qr_gate.py::test_just_a_few_seconds_late_still_costs_one_started_hour`.
- **Bugs removed:** the old code floored minutes, so a 30-second overstay created a penalty of 0, and it created the penalty after the booking was already marked completed.

## Platform and operations

### 14. Brute-force and abuse
- **How we handle it:** scoped rate limits on login/registration, booking and payment endpoints (`ScopedRateThrottle`); webhooks and the health check are exempt so providers are never throttled.
- **Proof:** `test_demo.py::TestRateLimiting`.

### 15. Geocoding provider is slow or down
- **How we handle it:** timeouts, network errors and invalid JSON all return "no results" instead of a 500.
- **Proof:** `test_societies_services.py` (URL error, timeout, OS error, invalid JSON).

### 16. Checkout return URL when apps live under a sub-path
- **Scenario:** after Stripe checkout the browser must come back to the app at `/user/#/bookings/<id>`, not to a path the site does not have.
- **How we handle it:** the return URL keeps the configured sub-path and uses the apps' hash routing.
- **Proof:** `test_payment_creation.py::test_checkout_returns_to_the_hash_route_of_the_app`.

### 17. A demo account that cannot book *(found on the live site)*
- **Scenario:** the seeded demo resident had an unpaid overstay penalty, and unpaid penalties block new bookings, so the one-tap demo login could not book.
- **How we handle it:** the seeded penalty belongs to a different resident.
- **Proof:** `test_demo.py::test_the_demo_resident_has_no_unpaid_penalty_blocking_new_bookings`.

### 18. Destructive demo endpoints in production
- **How we handle it:** `reset-demo` and `fast-forward` return 404 unless `DEMO_MODE=true`; reset also needs a constant-time-compared bearer token, and fast-forward needs a super admin.
- **Proof:** `test_demo.py::TestResetEndpoint`, `TestFastForward`.
