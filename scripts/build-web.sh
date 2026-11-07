#!/usr/bin/env bash
# Build all Flutter apps for web. Usage: scripts/build-web.sh <API_BASE_URL> [DEMO_MODE]
set -euo pipefail
API_BASE_URL="${1:?usage: build-web.sh <API_BASE_URL> [DEMO_MODE]}"
DEMO_MODE="${2:-false}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist"
rm -rf "$OUT" && mkdir -p "$OUT"

build() { # <app dir> <base-href path>
  (cd "$ROOT/mobile/apps/$1" && flutter build web --release \
    --base-href "/$2/" \
    --dart-define=API_BASE_URL="$API_BASE_URL" \
    --dart-define=DEMO_MODE="$DEMO_MODE" \
    ${MAPTILER_API_KEY:+--dart-define=MAPTILER_API_KEY="$MAPTILER_API_KEY"})
  mkdir -p "$OUT/$2" && cp -R "$ROOT/mobile/apps/$1/build/web/." "$OUT/$2/"
}

(cd "$ROOT/mobile" && flutter pub get)
build user_app user
build admin_app admin
build owner_app owner
build guard_app guard
build super_admin_app super-admin
echo "Built into $OUT"
