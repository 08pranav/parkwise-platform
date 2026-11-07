# ParkWise

Smart society parking platform: residents and visitors find and book parking
slots in housing societies, pay online, enter through a QR gate checked by
guards, and get penalties for overstays.

> Originally developed at `Parkingapp-crce/Parkingapp` during our internship.

Built by **Pranav Koradiya, Santo Xavier and Junaid Momin** as SDE interns at
Specter Technology and Games Pvt. Ltd. (Feb-Jun 2026), mentored by
**Dr. Sanket Jack**.

## Repository layout

| Path | What |
|---|---|
| `backend/` | Django + DRF API, Celery tasks |
| `mobile/apps/` | Flutter apps: `user_app`, `owner_app`, `admin_app`, `guard_app`, `super_admin_app` |
| `mobile/packages/core/` | Shared API client, auth, models, theme, widgets |
| `docs/` | Architecture notes and decisions |

## Quick start

```sh
make install   # backend + Flutter dependencies
make dev       # Postgres + Redis in Docker, migrate, run the API on :8000
make test      # backend tests
make analyze   # Flutter analyze
```

A full README (architecture, features, demo, edge cases) follows in a later phase.

## License

MIT. See [LICENSE](LICENSE).
