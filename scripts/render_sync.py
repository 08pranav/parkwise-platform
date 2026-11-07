#!/usr/bin/env python3
"""Create or update the ParkWise API service on Render from .env.deploy, then deploy it.

Usage: scripts/render_sync.py [--env-file .env.deploy] [--no-deploy]

Secret values are read from the env file and sent to Render; they are never printed.
Optional keys in .env.deploy: SITE_ORIGIN (the Vercel URL, used for CORS and return URLs).
"""

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:  # python.org builds on macOS ship without a CA bundle
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

API = "https://api.render.com/v1"
SERVICE_NAME = "parkwise-api"
REPO = "https://github.com/08pranav/parkwise-platform"

# Copied verbatim from .env.deploy into the service environment.
PASS_THROUGH = [
    "SECRET_KEY", "QR_SIGNING_SECRET", "DEMO_RESET_TOKEN",
    "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "REDIS_URL",
    "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET",
    "RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET",
    "MAPTILER_API_KEY",
]


def read_env(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def call(token, method, path, body=None):
    request = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60, context=SSL_CONTEXT) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode()[:400]
        sys.exit(f"Render API {method} {path} failed: {error.code} {detail}")


def build_env_vars(env):
    site = env.get("SITE_ORIGIN", "")
    static = {
        "PYTHON_VERSION": "3.13.0",
        "DJANGO_SETTINGS_MODULE": "parking_platform.settings.production",
        "DEMO_MODE": "true",
        "ALLOWED_HOSTS": ".onrender.com",
        "CORS_ALLOWED_ORIGINS": site,
        "CSRF_TRUSTED_ORIGINS": site,
        "FRONTEND_BASE_URL": f"{site}/user" if site else "",
    }
    merged = {**{k: env[k] for k in PASS_THROUGH if env.get(k)}, **static}
    return [{"key": k, "value": v} for k, v in merged.items() if v != ""]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=str(Path(__file__).resolve().parent.parent / ".env.deploy"))
    parser.add_argument("--no-deploy", action="store_true")
    args = parser.parse_args()

    env = read_env(args.env_file)
    token = env["RENDER_API_KEY"]
    workspace = env["RENDER_WORKSPACE_NAME"]

    owners = call(token, "GET", "/owners?limit=50")
    owner = next((o["owner"] for o in owners if o["owner"]["name"] == workspace), None)
    if owner is None:
        sys.exit(f"Render workspace '{workspace}' not found.")

    found = call(token, "GET", f"/services?name={SERVICE_NAME}&ownerId={owner['id']}&limit=5")
    service = next((s["service"] for s in found if s["service"]["name"] == SERVICE_NAME), None)
    env_vars = build_env_vars(env)

    if service is None:
        created = call(token, "POST", "/services", {
            "type": "web_service",
            "name": SERVICE_NAME,
            "ownerId": owner["id"],
            "repo": REPO,
            "branch": "main",
            "autoDeploy": "yes",
            "rootDir": "backend",
            "envVars": env_vars,
            "serviceDetails": {
                "runtime": "python",
                "plan": "free",
                "region": "singapore",
                "healthCheckPath": "/api/health/",
                "envSpecificDetails": {
                    "buildCommand": "pip install -r requirements.txt && python manage.py collectstatic --noinput",
                    "startCommand": "./start.sh",
                },
            },
        })
        service = created["service"]
        print(f"Created service {service['id']}")
    else:
        call(token, "PUT", f"/services/{service['id']}/env-vars", env_vars)
        print(f"Updated {len(env_vars)} environment variables on {service['id']}")
        if not args.no_deploy:
            call(token, "POST", f"/services/{service['id']}/deploys", {})

    url = service["serviceDetails"]["url"]
    print(f"URL: {url}")
    if args.no_deploy:
        return

    for _ in range(90):
        deploys = call(token, "GET", f"/services/{service['id']}/deploys?limit=1")
        status = deploys[0]["deploy"]["status"] if deploys else "unknown"
        print(f"  deploy status: {status}")
        if status == "live":
            return
        if status in {"build_failed", "update_failed", "canceled", "pre_deploy_failed"}:
            sys.exit(f"Deploy ended with status {status}. See the Render dashboard logs.")
        time.sleep(20)
    sys.exit("Timed out waiting for the deploy to go live.")


if __name__ == "__main__":
    main()
