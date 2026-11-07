import ssl

from .base import *  # noqa: F401, F403

DEBUG = False

# Required in production: no insecure fallbacks.
SECRET_KEY = env("SECRET_KEY")
QR_SIGNING_SECRET = env("QR_SIGNING_SECRET")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

if env("DATABASE_URL", default=""):
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST"),
            "PORT": env("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"sslmode": "require"},
        }
    }

CORS_ALLOW_ALL_ORIGINS = False
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Render terminates TLS at its proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Celery: Upstash exposes rediss:// and needs TLS options.
CELERY_BROKER_CONNECTION_TIMEOUT = 5
CELERY_BROKER_CONNECTION_MAX_RETRIES = 3
CELERY_REDIS_RETRY_ON_TIMEOUT = True
CELERY_REDIS_MAX_CONNECTIONS = 10
CELERY_RESULT_BACKEND_MAX_RETRIES = 3
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
if CELERY_BROKER_URL.startswith("rediss://"):  # noqa: F405
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

# drf-spectacular reports schema-quality warnings (views without a serializer_class,
# querysets that read request.user). They affect the generated docs only, not security,
# and are tracked as documentation debt.
SILENCED_SYSTEM_CHECKS = ["drf_spectacular.W001", "drf_spectacular.W002"]
