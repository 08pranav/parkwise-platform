#!/usr/bin/env bash
# One-command redeploy of the whole demo from .env.deploy.
#   1. sync environment variables to Render and deploy the API
#   2. build every Flutter web app against the live API
#   3. assemble the site (landing page + apps) and deploy it to Vercel
# Usage: scripts/deploy.sh [api|web|all]   (default: all)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a; . ./.env.deploy; set +a
TARGET="${1:-all}"
PY="${PYTHON:-python3}"

if [[ "$TARGET" == "api" || "$TARGET" == "all" ]]; then
  "$PY" scripts/render_sync.py
fi

API_URL="$("$PY" - <<'PYEOF'
import json, os, ssl, urllib.request
try:
    import certifi; ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    ctx = ssl.create_default_context()
req = urllib.request.Request("https://api.render.com/v1/services?name=parkwise-api&limit=5",
    headers={"Authorization": "Bearer " + os.environ["RENDER_API_KEY"]})
data = json.load(urllib.request.urlopen(req, context=ctx))
print(data[0]["service"]["serviceDetails"]["url"])
PYEOF
)"
echo "API: $API_URL"

if [[ "$TARGET" == "web" || "$TARGET" == "all" ]]; then
  scripts/build-web.sh "$API_URL" true
  scripts/assemble-site.sh "$API_URL"
  (cd dist && npx --yes vercel@latest deploy --prod --yes --token "$VERCEL_TOKEN" --name parkwise)
fi
