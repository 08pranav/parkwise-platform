# Reconciliation report: local presentation copy vs original remote

Date: 2026-11-07. Sources compared:

- **Local**: the clone used for the presentation, `master` at `25a6872` (2026-06-19), plus one stash and one untracked file.
- **Remote**: `origin/master` of `Parkingapp-crce/Parkingapp` (read-only), at `9ebdbc3` (2026-06-22).

## Inventory

| Item | Finding |
|---|---|
| Local-only commits | **0**. `git rev-list --left-right --count master...origin/master` printed `0 13`. |
| Remote-only commits | **13**, 2026-06-20 to 2026-06-22 (surge pricing, mock-payment removal, premium user_app revamp, super-admin refund/rollback, owner approval, booking detail with Stripe and Razorpay, vehicles screen, guards screen, dark-mode fixes, API docs). |
| Uncommitted changes | none tracked. Untracked: `.env.deploy` (secrets, never committed) and `backend/apps/payments/CorporateActions.code-workspace` (editor file, junk). |
| Stashes | 1: `WIP on pranav` on `43850ab` (2026-04-23): `user_app` `home_screen.dart`, `societies_cubit.dart`, `router.dart`. |
| Local branch `pranav` | contains no commit that `master` lacks. |

All of the above is preserved on branch `backup/presentation-local-2026-11-07`. The stash touches files the remote rewrote in June, so its two conflicting files were committed there in their stashed form.

## Diff summary (local `master` to remote `master`)

| Area | Change |
|---|---|
| `backend/` | 15 files, +620 / -85 |
| `parkwise_backend/` | no change |
| `mobile/apps/*` | 32 files, +5568 / -2030 |
| `mobile/packages/core` | 4 files, +25 |
| `park_app`, `park_guard` | no change |
| `park_admin` | 1 file, +65 |
| `park_owner` | 6 files, +275 / -225 |
| `docs/` | 1 file, +153 |

## Configuration names each version relies on (names only)

- Backend settings read: `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `REDIS_URL`, `QR_SIGNING_SECRET`, `MAPTILER_API_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `FRONTEND_BASE_URL`, geocoding URL and user-agent settings. Same in both versions.
- Local `backend/.env` also defines `DATABASE_URL` and `JWT_SECRET`, which the settings do not read.
- Apps: API base URL comes from `core` `env_config.dart` (hard-coded localhost / Android emulator defaults plus placeholder staging and production hosts). Same in both versions.

## Test results (throwaway Postgres 16 and Redis 7 in Docker)

| Check | Local | Remote |
|---|---|---|
| Backend `manage.py check` | clean | clean |
| Backend `migrate` | ok | ok |
| Backend server: schema and docs 200, register ok | works | works (new users start as `pending` approval) |
| Backend automated tests | 0 tests exist | 0 tests exist |
| `user_app` pub get / analyze / build web | ok / 7 issues, 0 errors / ok | ok / 7 issues, 0 errors / ok |
| `admin_app` | ok / 13 issues, 0 errors / ok | ok / 16 issues, 0 errors / ok |
| `guard_app` | ok / clean / ok | ok / clean / ok |
| `super_admin_app` | ok / 8 issues, 0 errors / ok | ok / **clean** / ok |
| `park_owner` | ok / 17 issues, **1 error** / ok | ok / 10 issues, 0 errors / ok |

Playwright walkthroughs are not repeated for the local copy: it is a strict ancestor of the remote, so only the merged result is exercised in the later phases.

## Merge decisions

The default is the local version. Here local differs from remote only by being older, so:

1. **Base = remote `master`.** It is a strict superset of local commits, builds everywhere, and has fewer analyzer errors (`super_admin_app` clean, `park_owner` error fixed).
2. **Local stash not applied.** It is an April WIP of `home_screen.dart` that the June premium revamp replaced. It stays on the backup branch.
3. **`.gitignore` from local backup kept** (adds deploy secrets, keystores, `.vercel/`).
4. **`CorporateActions.code-workspace` dropped** from the working tree (editor junk, kept on the backup branch).
