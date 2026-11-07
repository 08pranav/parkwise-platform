# ADR 0001: App structure

Status: accepted, 2026-11-07

## Context

ParkWise started as separate prototypes (`park_app`, `park_admin`, `park_guard`,
`park_owner`) on an older Node-then-Django backend (`parkwise_backend`), then
moved to a Melos monorepo (`mobile/`) on the current Django backend (`backend/`).
Both generations lived side by side in the repository.

The monorepo had four apps (user, society admin, guard, super admin). The owner
app still lived outside it as `park_owner`, mixing calls to the current API with
calls to endpoints that only existed in the old backend.

Size of each Flutter app before this change (Dart lines, `git ls-files`):

| App | Dart lines |
|---|---|
| `mobile/apps/user_app` | 8,758 |
| `mobile/apps/admin_app` | 5,786 |
| `mobile/apps/super_admin_app` | 4,308 |
| `mobile/apps/guard_app` | 1,967 |
| `park_owner` (legacy) | 2,400 |

## Options considered

1. **Keep five role apps** in one monorepo, sharing the `core` package.
2. **Merge some roles** (for example owner into user, since an owner is a
   resident user who lists their own slot).
3. **One role-based app** that shows different screens after login.

## Decision

Keep **five apps**: `user_app`, `owner_app`, `admin_app` (society admin),
`guard_app`, `super_admin_app`, all on the shared `core` package.

- **Different audiences and devices.** Residents and visitors use phones; guards
  use a phone or tablet at the gate with a camera scanner; admins and the super
  admin work on desktop-sized screens. One binary for all would ship camera,
  map and payment code to people who never use them.
- **Keep user and guard separate.** The guard app only needs sign-in and QR
  scanning, and a gate device should not be able to book or pay.
- **Blast radius.** A bug in the refund screen of the super admin app cannot
  break the booking flow of the user app.
- **Cost of five apps is low** because auth, API client, token storage, theme
  and common widgets live once in `core`.

`owner_app` stays separate from `user_app` for now: its job (list a slot, wait
for approval, open or close it) is small and distinct. Owners sign in with a
resident (`user`) account, as the backend models them.

## Consequences

- `park_app`, `park_admin`, `park_guard`, `park_owner` and `parkwise_backend`
  are deleted. Their git history remains.
- `owner_app` was rebuilt on `core` (auth bloc, secure token store, API client,
  theme) and no longer uses SharedPreferences for tokens.
- All apps read the backend origin from `--dart-define=API_BASE_URL`.

## Roadmap items from the legacy prototypes

The legacy prototype had two features that the current backend never
implemented. They are not ported now; they are kept as roadmap items:

- **Wallet** (`park_app` `wallet_page.dart`): stored balance for payments and refunds.
- **OTP password reset** (forgot password, verify OTP, reset password): needs an
  email or SMS provider, which the free-tier deployment does not include.
