# Contributing

ParkWise was written by Pranav Koradiya, Santo Xavier and Junaid Momin as SDE interns at Specter Technology
and Games Pvt. Ltd. Contributions are welcome.

## Set up

```sh
make install     # backend and Flutter dependencies
make dev         # PostgreSQL + Redis in Docker, migrations, API on :8000
make worker      # Celery worker with beat (optional locally)
```

Flutter apps read their configuration at build time:

```sh
cd mobile/apps/user_app
flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Copy `backend/.env.example` to `backend/.env` for local settings. Never commit real keys:
`.env`, `.env.*`, keystores and `.vercel/` are git-ignored, and gitleaks runs in pre-commit and CI.

## Before you open a pull request

```sh
make lint          # ruff check + format check
make test          # backend tests (needs `make infra`)
make analyze       # flutter analyze --fatal-infos, every package
make flutter-test
```

Install the hooks once: `pip install pre-commit && pre-commit install`.

## Conventions

- **Backend:** thin views, business rules in `services.py`, money as `Decimal`, times as aware datetimes, every booking status change through `bookings.state_machine.transition`. New behaviour needs a test; payment and booking changes need an edge-case test.
- **Flutter:** shared code goes in `mobile/packages/core`; apps never hard-code the API URL; state management is bloc/cubit.
- **Git:** one branch per change, a pull request, green CI, squash merge. Do not force-push `main`.
- **Commits:** short imperative subject, explain the why in the body.

## Reporting a security issue

Please do not open a public issue for a vulnerability. Contact a maintainer through their GitHub profile.
