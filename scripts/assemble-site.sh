#!/usr/bin/env bash
# Assemble dist/ (landing page + every web app + vercel.json). Run after build-web.sh.
# Usage: scripts/assemble-site.sh <RENDER_API_ORIGIN>   e.g. https://parkwise-api.onrender.com
set -euo pipefail
API_ORIGIN="${1:?usage: assemble-site.sh <api origin>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist"
cp "$ROOT"/web/landing/* "$OUT/"
cat > "$OUT/vercel.json" <<JSON
{
  "cleanUrls": false,
  "rewrites": [
    { "source": "/api/:path*", "destination": "${API_ORIGIN}/api/:path*" },
    { "source": "/user/:path*", "destination": "/user/index.html" },
    { "source": "/owner/:path*", "destination": "/owner/index.html" },
    { "source": "/admin/:path*", "destination": "/admin/index.html" },
    { "source": "/guard/:path*", "destination": "/guard/index.html" },
    { "source": "/super-admin/:path*", "destination": "/super-admin/index.html" }
  ]
}
JSON
echo "Site assembled in $OUT"
