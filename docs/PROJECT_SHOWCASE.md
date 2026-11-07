# ParkWise: project showcase brief

A fact-checked brief for writing posts about ParkWise. Every number below comes from a command run on this
repository or from the live deployment. Anything not yet produced is marked **not available**. Statistics about
the parking problem in general are **not** included; add one only if you can source it ("verify before posting").

## 1. One-liner and pitch

**One-liner:** ParkWise is a smart-parking platform for housing societies: book a slot, pay online, enter through a QR gate.

**Pitch:** We built ParkWise as our internship project at Specter Technology and Games Pvt. Ltd. (Feb to Jun 2026),
mentored by Dr. Sanket Jack. Residents and visitors book and pay for a slot, guards admit them with a signed QR code,
and overstays are charged automatically. The interesting part turned out to be the edge cases: double bookings,
duplicate payment webhooks, refunds, QR replays and time zones.

## 2. The problem

Our own observations about society parking (not statistics):

- **Residents and visitors:** can't tell which slots are free; visitors circle, owners can't safely rent a spare slot.
- **Guards:** check names in a register at the gate, which is slow and leaves no reliable record.
- **Owners and admins:** disputes about who stayed how long and who owes what have nothing to settle them.

## 3. Our solution, role by role

1. **Resident:** search near a destination, see a surge-priced quote, choose a slot and window, add a vehicle, pay (Stripe or Razorpay), receive a signed QR.
2. **Slot owner:** list a spare slot with its daily hours, wait for admin approval, open or close it.
3. **Society admin:** approve residents and slots, manage inventory and availability windows, add guards and grant scan rights.
4. **Guard:** scan the QR (or type the code if the camera fails); the system checks society, time window and payment, logs the scan, and refuses a repeat.
5. **Super admin:** onboard societies, look up a booking and refund its payment in full or in part.

## 4. The edge cases that were the real problems

Full list with tests: [EDGE_CASES.md](EDGE_CASES.md). The ones that make the best stories:

| Problem | What broke or could break | What we did | The lesson |
|---|---|---|---|
| Concurrency | Eight people booking one slot at once all saw "free" | Row lock on the slot inside one transaction; a test fires 8 threads and expects one winner | We deleted the lock to check the test: it failed 3 of 3 runs. A concurrency test is only trustworthy once you have seen it fail |
| Webhooks | Anyone could POST a fake "payment failed" event; providers redeliver; events arrive out of order | Signed and fail-closed; each event stored under a unique id; a captured payment is never downgraded | Treat a public webhook as hostile input, and make every handler safe to run twice |
| Late payment | A card charged at minute 6 of a 5-minute lock | Revive the booking if the slot is free, otherwise refund automatically | Money arriving "too late" is a normal case, not an error |
| Refunds | Two admins refunding at once; a gateway error after deciding to refund | Reserve the amount under a lock, call the gateway with an idempotency key, audit every attempt | Write the intent down before you call the outside world |
| QR gate | Replay, screenshots of old codes, wrong society | Signed token that must match the stored one; one entry per booking; every scan logged | Replay protection fell out of the state machine rather than needing a separate store |
| Surge pricing | Float and Decimal mixed; thresholds ambiguous | Pure Decimal functions; strict thresholds; every boundary tested | A price people pay should be a function you can unit test |
| Time zones | Windows are wall-clock in IST; a 04:30 UTC request is 10:00 IST; bookings cross midnight | Convert to local time and split at local midnight | Our first midnight test caught an off-by-a-microsecond bug before any user did |
| Overstay | A 30-second overstay produced a penalty of zero; a retry could charge twice | Round up, create the penalty in the exit transaction, one per booking enforced by the database | Rounding rules are product decisions, so write them down |

## 5. Architecture and why

- **Django + DRF:** fast to build, strong transaction and row-lock support, thin views with business rules in `services.py` so they are testable without HTTP.
- **PostgreSQL:** real row locks and constraints (the concurrency guarantee depends on it).
- **Celery + Redis:** unpaid-booking expiry and no-show detection; a per-booking task plus a sweep, because a single scheduled task can be lost.
- **Stripe and Razorpay:** both mainstream in India-facing products; both behind the same capture and refund functions.
- **Flutter monorepo:** five role apps (different devices and audiences) share one `core` package for API client, auth, models and theme.
- **Free hosting:** Supabase, Upstash, Render, Vercel; see [DEPLOYMENT.md](DEPLOYMENT.md).

## 6. From internship code to production-grade

| | Before | After | How measured |
|---|---|---|---|
| Backends | 2 (`backend/` and the old `parkwise_backend/`) | 1 | directory listing at the reconciled commit vs `main` |
| Flutter apps | 8 (4 legacy `park_*` + 4 in the monorepo) | 5, all in one monorepo on a shared `core` package | same |
| Dart lines in legacy apps | 10,220 | 0 (deleted) | `wc -l` over the four folders at the reconciled commit |
| Old backend (Python lines) | 1,495 | 0 (deleted) | same |
| Backend Python lines | 6,688 | 9,766 (of which 2,222 are tests, 6,100 app code excluding migrations) | `git ls-tree` + `wc -l` at the reconciled commit vs `HEAD` |
| Flutter app lines | 20,819 | 22,753 (includes the new owner app and 655 lines of tests) | same |
| Backend tests | 0 (six empty `tests.py` stubs) | 236 | `pytest` |
| Backend coverage | none | 96.6% of `services.py`, 74.2% overall | `pytest --cov` |
| Flutter tests | 1 small `core` test and 4 placeholders (`expect(true, isTrue)`) | 37 | counted `test(` and `testWidgets(` |
| Analyzer findings | 33 (core 10, user_app 7, admin_app 16) | 0 with `--fatal-infos` in every package | `flutter analyze` before and after |
| Repo size (`.git`) | 46 MB (committed binaries: ngrok, Stripe CLI) | 7.8 MB | `du -sh .git`, history cleaned with `git filter-repo`, authors and dates kept |
| Secrets in history | a Django key, a Razorpay test key, a MapTiler key, database credentials | removed and replaced with `***REMOVED***` | gitleaks plus a scan of every blob in every encoding |
| CI | none | 3 jobs per pull request (backend, Flutter, gitleaks) | `.github/workflows/` |
| API | undocumented in code | 55 paths, 71 operations, generated reference | `manage.py spectacular` |
| Deployment | local only | live on four free services; nightly reset; keep-warm | [DEPLOYMENT.md](DEPLOYMENT.md) |

Honest caveat: three Flutter screens are still very large (`home_screen.dart` 2,196 lines, `refund_screen.dart` 1,604,
`booking_detail_screen.dart` 1,442). Splitting them into feature folders is on the roadmap, not done.

## 7. Other measured facts

- 65 commits on `main` in the new repository (the original history was kept; original authors and dates preserved).
- Live check: `scripts/smoke-live.mjs` runs 31 checks against the deployed API: all five roles sign in, a real Stripe test-card payment, QR entry, replay rejected, forced overstay with a penalty, a real Stripe refund, a Razorpay order and a signed Razorpay webhook. All 31 passed on the last run.
- Videos: **not available** in this pass. Screenshots and a GIF: **not available**. Android APKs: **not available**.

## 8. Skills demonstrated

Transactional design and row locking; idempotency; payment-gateway integration (webhooks, signatures, refunds);
state machines; time-zone-correct date handling; Celery task design; REST API design with role-based permissions;
property and boundary testing; Flutter architecture with a shared package and bloc/cubit; CI with Postgres and Redis
services; secret scanning and git history rewriting; free-tier deployment (Render, Vercel, Supabase, Upstash).

## 9. Limitations and roadmap, honestly

- Payments run in **test mode**; no real money moves.
- The API is on a free tier: after about 15 minutes idle the first request takes around a minute (a 10-minute keep-warm ping reduces this but does not remove it).
- The data is a **fictional demo dataset** that resets nightly.
- Three screens still need splitting; some endpoints lack request/response schemas in the OpenAPI docs.
- Wallet balance and OTP password reset were in the first prototype and are not in the current product.
- Android APKs and the demo videos are not produced yet.

## 10. Links

- Live demo: https://parkwise-alpha.vercel.app
- API docs (Swagger): https://parkwise-api-77gc.onrender.com/api/docs/
- Repository: https://github.com/08pranav/parkwise-platform
- Edge cases: https://github.com/08pranav/parkwise-platform/blob/main/docs/EDGE_CASES.md
- APK release, videos, GIF, screenshots: **not available yet**

## 11. LinkedIn material

### Five hooks

1. **Problem-first:** "A society gate, a paper register and 200 cars. That's how most parking still works."
2. **Edge-case story:** "Eight people tapped 'Book' on the same parking slot at the same millisecond. Our first version let all eight in."
3. **Result-first:** "We turned an internship project into a deployed app with 236 tests, CI and a live demo."
4. **Contrarian:** "The hard part of a parking app isn't the app. It's the money, the clock and the double click."
5. **Question:** "What should happen when a customer pays for a parking slot six minutes after it was released?"

### Post draft A: the internship journey (about 210 words)

For five months this year, the three of us (Pranav Koradiya, Santo Xavier and Junaid Momin) worked as SDE interns at
Specter Technology and Games Pvt. Ltd., mentored by Dr. Sanket Jack. Our project: ParkWise, a smart-parking platform for
housing societies.

Residents book and pay for a slot, guards admit them with a signed QR code, and overstays are charged automatically.
It is a Django API with a Flutter app for each role: resident, slot owner, society admin, guard and super admin.

When the internship ended we kept going. We merged two backends and eight Flutter apps into one backend and five apps
on a shared package, wrote 236 backend tests, cleaned secrets and binaries out of the git history (46 MB down to 7.8 MB),
set up CI, and deployed it on free tiers.

What surprised us most was that the real work wasn't the screens. It was concurrency, payment webhooks, refunds and
time zones.

Thank you, Dr. Sanket Jack, for pushing us to ask "what happens when this fails?" and not only "does it work?".

Live demo (test payments only): https://parkwise-alpha.vercel.app
Code: https://github.com/08pranav/parkwise-platform

#Flutter #Django #SoftwareEngineering #Internship

### Post draft B: engineering deep-dive on one edge case (about 220 words)

Our parking app let eight people book the same slot at the same time. Here is how we found out and fixed it.

A booking request does two things: check that the slot is free, then save the booking. Run eight requests in
parallel and all eight pass the check before any of them saves. Nothing crashed. The database simply held eight
bookings for one slot.

The fix is small: lock the slot's row inside the transaction (`select_for_update`), so requests for that slot run one
after another and the later ones see the earlier booking.

The part we are proudest of is the test. It starts eight threads at the same instant and asserts that exactly one
succeeds. Then we did the step people skip: we removed the lock and ran the test again. It failed three runs out of three.
Only then did we trust it.

The same habit shaped the rest of the backend: duplicate payment webhooks are ignored by event id, a payment that
arrives after its booking expired either revives the booking or is refunded, and two admins refunding at once
reach the payment gateway exactly once.

The full list is in the repo's EDGE_CASES.md, each one linked to its test.

https://github.com/08pranav/parkwise-platform

#Django #PostgreSQL #BackendDevelopment #Testing

### Post draft C: "try it live" (about 150 words)

You can try ParkWise right now, no sign-up.

It is a parking platform for housing societies: book a slot, pay, get a QR code, and a guard scans it at the gate.

Open the demo and press "Try as Resident". Pay with the Stripe test card 4242 4242 4242 4242. Then open the guard app
and enter the booking's code to see entry granted, and scan it again to see the replay refused.

Everything is test mode and the data resets nightly. It runs on free tiers, so if it is asleep the first load takes
about a minute.

Built by Pranav Koradiya, Santo Xavier and Junaid Momin during our SDE internship at Specter Technology and Games
Pvt. Ltd., mentored by Dr. Sanket Jack.

Demo: https://parkwise-alpha.vercel.app
Code: https://github.com/08pranav/parkwise-platform

#Flutter #Django #OpenSource

### Carousel outline (8 slides)

1. Title: "ParkWise: smart parking for housing societies" (logo, live demo link).
2. The problem: free slots nobody can see, a paper register at the gate.
3. The five roles and what each does.
4. Architecture: Flutter apps, Django API, Postgres, Redis, Stripe and Razorpay (the diagram from the README).
5. Edge case 1: eight people, one slot (before and after the lock).
6. Edge case 2: webhooks arrive twice, late and out of order.
7. From prototype to production-grade: the before/after table from section 6.
8. Try it live, team credit, mentor thanks, links.

### Video post caption

**Not available yet** (no video has been produced). When one exists, use this structure and fill in the real timestamps:
"ParkWise: smart parking for housing societies. Chapters: 0:00 overview, then super admin, owner and society admin,
resident booking with surge pricing and a Stripe test payment, guard scan with replay protection, overstay penalty,
refund, dark mode. Built by Pranav Koradiya, Santo Xavier and Junaid Momin at Specter Technology and Games Pvt. Ltd.,
mentored by Dr. Sanket Jack."

### Tagging

- Company: **Specter Technology and Games** (search the company page and tag it from the post editor).
- Mentor: **Dr. Sanket Jack**. Teammates: **Santo Xavier** and **Junaid Momin**. Tag each from the post editor so LinkedIn links their profiles; confirm each profile is the right person before posting.
- Hashtags: 3 to 5 only, for example #Flutter #Django #SoftwareEngineering.

### Instructions for the AI writing the post

- Voice: an early-career software developer, plain and specific. First person plural ("we").
- Credit the whole team equally: Pranav Koradiya, Santo Xavier, Junaid Momin. **Never say who did what.** For "what was your role?" the answer is "we worked across the full stack together".
- Frame it as an internship project at Specter Technology and Games Pvt. Ltd. (Feb to Jun 2026) and thank Dr. Sanket Jack.
- Lead with the problem, the solution, or one edge case. Use only the numbers in this file.
- Do not overclaim: payments are test mode, the data is fictional, the service sleeps on the free tier, and some screens are still large.
- Do not state statistics about parking in general unless the user gives a source.
- End with the live link and the repository link, then 3 to 5 hashtags.

## 12. FAQ for recruiters and engineers

**What was your role?** We worked across the full stack together: backend, Flutter apps, payments, testing and deployment.

**What was the hardest part?** Making money and time behave: concurrency on booking, idempotent payment webhooks, refunds,
and time zones. See EDGE_CASES.md.

**How did you test it?** 236 backend tests on PostgreSQL (including multi-threaded race tests), 37 Flutter tests, and a
31-check live smoke test that pays with a real Stripe test card in a headless browser.

**Is it production-ready?** It is production-shaped (CI, secret scanning, idempotent payments, deploy checks) but it runs
in test mode on free tiers with a demo dataset. Real money would need live keys, invoicing and a paid database plan.

**Why five apps instead of one?** Different audiences and devices; a gate device should not be able to book or pay.
See ADR 0001.

**Why Django?** Transactions and row locks, a mature ecosystem, and thin views over testable services.

**What would you do next?** Split the three largest Flutter screens, finish the OpenAPI schemas, add the wallet and OTP password reset, and produce the demo video and Android releases.
