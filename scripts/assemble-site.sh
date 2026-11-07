#!/usr/bin/env bash
# Assemble dist/ (landing page + every web app + vercel.json). Run after build-web.sh.
# Usage: scripts/assemble-site.sh <API_ORIGIN>  (kept for the signature; the apps call the API directly with CORS)
set -euo pipefail
API_ORIGIN="${1:?usage: assemble-site.sh <api origin>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist"
cp "$ROOT"/web/landing/* "$OUT/"
cat > "$OUT/vercel.json" <<JSON
{
  "routes": [
    { "handle": "filesystem" },
    { "src": "/user/.*", "dest": "/user/index.html" },
    { "src": "/owner/.*", "dest": "/owner/index.html" },
    { "src": "/admin/.*", "dest": "/admin/index.html" },
    { "src": "/guard/.*", "dest": "/guard/index.html" },
    { "src": "/super-admin/.*", "dest": "/super-admin/index.html" }
  ]
}
JSON
echo "Site assembled in $OUT"
