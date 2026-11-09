# LinkedIn hand-off

Everything needed to announce ParkWise: the facts, ready-to-use post drafts, which media file goes where, and the
questions people are likely to ask. All numbers come from the repository and the live site as of the v1.0.0 release.

## Links

| What | URL |
|---|---|
| Code | https://github.com/08pranav/parkwise-platform |
| Live demo (five apps) | https://parkwise-alpha.vercel.app |
| API docs (Swagger) | https://parkwise-api-77gc.onrender.com/api/docs/ |
| Android APKs and demo videos | https://github.com/08pranav/parkwise-platform/releases/tag/v1.0.0 |

The API runs on a free tier. After a quiet period the first request can take about a minute, so open the live demo
yourself once, a few minutes before posting.

## The project in five lines

- ParkWise lets residents and visitors book parking inside housing societies, pay online, and enter through a QR gate.
- Five Flutter apps (resident, slot owner, society admin, guard, super admin) share one Django REST API.
- Payments run through Stripe and Razorpay in test mode. Guards scan a signed QR code; late exits are charged an overstay penalty.
- 238 backend tests, 40 Flutter tests, and a live smoke test of 31 checks, including a real Stripe test-card payment.
- Hosted entirely on free tiers: Supabase, Render, Upstash and Vercel.

## Facts you can safely quote

| Claim | Where it comes from |
|---|---|
| 5 Flutter apps, 1 Django API | `mobile/apps/`, `backend/` |
| 238 backend tests (pytest, PostgreSQL) | `make test` |
| 96.6% line coverage of the `services.py` modules, 74% of the whole backend | `pytest --cov` |
| 40 Flutter unit and widget tests | `mobile/**/test` |
| 55 API paths, 71 operations | `docs/API_DOCUMENTATION.md` |
| 31 live smoke checks | `scripts/smoke-live.mjs` |
| Signed release APKs for all five apps | v1.0.0 release, with SHA-256 checksums |
| Built Feb to Jun 2026 as SDE interns at Specter Technology and Games Pvt. Ltd. | README |

## Do not claim

- That payments are real. They are test mode only.
- That the APKs were tested on a physical phone. They are built, signed and verified, not field-tested.
- That a real Razorpay webhook was received. The signed webhook path is tested with a simulated, correctly signed request.
- Anything about users, revenue or adoption. It is a demo.
- Who built which part. Credit is equal across the three of us.

## Post drafts

Pick one. Replace nothing in angle brackets except the tags; put the links in the first comment, not the post body.

### Draft A: the story (recommended)

> Three of us spent four months as SDE interns at Specter Technology and Games building a parking app for housing societies. This week it went from a working prototype to something you can open and use.
>
> A resident books a slot, pays, and gets a signed QR code. The guard scans it at the gate. If the car leaves late, the overstay penalty is worked out and charged. Society admins, slot owners and a super admin each have their own app.
>
> The screens were not the hard part. The edge cases were: eight people booking the same slot at once, a payment that lands after the booking has expired, a QR code scanned twice, a refund requested twice, an overstay that crosses midnight. Each one has a test.
>
> In numbers: 5 Flutter apps, 1 Django API, 238 backend tests, and a smoke test that runs 31 checks against the live site, including a real Stripe test-card payment.
>
> It all runs on free tiers, so the first request after a quiet spell can take a minute. Payments are test mode only.
>
> Built with <tag Santo Xavier> and <tag Junaid Momin>. Thank you, <tag Dr. Sanket Jack>, for the mentorship.
>
> Demo and code in the first comment.

**First comment:**

> Live demo (use the "Try as..." button on each login screen): https://parkwise-alpha.vercel.app
> Code and docs: https://github.com/08pranav/parkwise-platform
> Android APKs and the full walkthrough video: https://github.com/08pranav/parkwise-platform/releases/tag/v1.0.0

### Draft B: the problem first

> Parking in a housing society runs on goodwill and a paper register. Slots sit empty while visitors circle the block, gates back up while a guard checks a notebook, and nobody can settle who stayed how long.
>
> We built ParkWise to replace the register: search, a live price, pay online, a QR code at the gate, an automatic penalty if you overstay.
>
> Under the hood it is a Django API with five Flutter apps on top of it, and the part we are proudest of is the boring one. A booking can only move through a fixed set of states, two people cannot take the same slot, a webhook that arrives twice is applied once, and a refund cannot be paid out twice. 238 tests keep those promises.
>
> A team project from our internship at Specter Technology and Games, with Santo Xavier and Junaid Momin, and with guidance from Dr. Sanket Jack.
>
> Links in the first comment.

### Draft C: short

> We finished our internship project: ParkWise, parking for housing societies. Five Flutter apps, one Django API, test-mode Stripe and Razorpay, QR gate entry, automatic overstay penalties, 238 backend tests, live on free tiers.
>
> Made with Santo Xavier and Junaid Momin at Specter Technology and Games, mentored by Dr. Sanket Jack.
>
> Demo and code in the first comment.

### Suggested hashtags (pick three or four)

`#Flutter` `#Django` `#Python` `#SoftwareEngineering` `#Internship` `#OpenSource`

## Which media to attach

| Media | File | Use |
|---|---|---|
| Main post video, feed (square) | `ParkWise-highlight-square.mp4` | Attach to the post. About a minute, plays well on mobile |
| Vertical version | `ParkWise-highlight-tall.mp4` | For stories, shorts, reels |
| Full walkthrough | `ParkWise-full-wide.mp4` | Link from the first comment or a follow-up post |
| Chapters | `chapters.txt` | Paste into a video description |
| GIFs | `docs/assets/gifs/` | README, replies, comments |

All files are on the v1.0.0 release page. LinkedIn video limits and codecs change; if an upload is refused, re-encode
with `ffmpeg -i in.mp4 -c:v libx264 -crf 23 -pix_fmt yuv420p -c:a aac out.mp4`.

## Posting checklist

1. Open the live demo and the Swagger page once so the free-tier API is awake.
2. Check that the three links in the first comment open.
3. Tag Santo Xavier, Junaid Momin, Dr. Sanket Jack and Specter Technology and Games (the handles are yours to look up).
4. Post in the morning on a weekday, then reply to comments for the first hour.
5. Pin the repository on your GitHub profile, and add it to the LinkedIn Featured section.

## Questions you may get

**Is this production-ready?** No. It is a deployed, tested demo. Real-money payments would need live keys, tax invoices
and a production database plan (see the roadmap in the README).

**How do you stop double bookings?** The booking transaction locks the slot row, so two simultaneous requests are
serialised. A test fires eight at once and expects exactly one to win.

**What if a payment webhook arrives twice or late?** Webhooks are verified, de-duplicated by event id inside the same
database transaction, and never downgrade a captured payment. A payment that lands after its booking expired either
revives the booking or is refunded automatically.

**Why Flutter and Django?** One codebase per app for web and Android, and a mature framework for the transactional
core. More in [ARCHITECTURE.md](ARCHITECTURE.md).

**What would you do next?** Wallet balance, OTP password reset, splitting the three largest Flutter screens, full
request and response schemas in the OpenAPI document. See the roadmap in the README.

**Who did what?** All three of us contributed equally, across backend, apps, testing and deployment.
