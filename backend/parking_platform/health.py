import redis
from django.conf import settings
from django.db import connection
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView


def _check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def _check_redis():
    try:
        client = redis.from_url(
            settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2
        )
        return bool(client.ping())
    except Exception:
        return False


class HealthView(APIView):
    """Liveness/readiness probe used by Render and the keep-warm workflow.

    503 when the database is unreachable (the API cannot serve). When only Redis is
    down the API still serves requests, so it answers 200 with ``status: degraded``.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        db_ok = _check_database()
        redis_ok = _check_redis()
        if not db_ok:
            state, http_status = "unavailable", 503
        elif not redis_ok:
            state, http_status = "degraded", 200
        else:
            state, http_status = "ok", 200
        return Response({"status": state, "database": db_ok, "redis": redis_ok}, status=http_status)
