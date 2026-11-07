#!/usr/bin/env bash
# Render start command: apply migrations, then run the API and the Celery worker
# (with beat) side by side. The free plan has no background workers, so one
# service runs both processes under honcho.
set -euo pipefail
python manage.py migrate --noinput
exec honcho start
