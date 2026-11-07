#!/usr/bin/env bash
# Build signed release APKs for the five apps into dist-apk/.
# Needs mobile/apps/*/android/key.properties (git-ignored; see docs/DEPLOYMENT.md).
# Usage: scripts/build-apks.sh <API_BASE_URL> [version]
set -euo pipefail
API_BASE_URL="${1:?usage: build-apks.sh <API_BASE_URL> [version]}"
VERSION="${2:-1.0.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist-apk"
rm -rf "$OUT" && mkdir -p "$OUT"
(cd "$ROOT/mobile" && flutter pub get)

build() { # <app dir> <file label>
  (cd "$ROOT/mobile/apps/$1" && flutter build apk --release \
    --dart-define=API_BASE_URL="$API_BASE_URL" \
    --dart-define=DEMO_MODE=true \
    ${MAPTILER_API_KEY:+--dart-define=MAPTILER_API_KEY="$MAPTILER_API_KEY"})
  cp "$ROOT/mobile/apps/$1/build/app/outputs/flutter-apk/app-release.apk" "$OUT/ParkWise-$2-v$VERSION.apk"
}

build user_app Resident
build owner_app Owner
build admin_app SocietyAdmin
build guard_app Guard
build super_admin_app SuperAdmin

(cd "$OUT" && shasum -a 256 *.apk > SHA256SUMS.txt)
echo "APKs in $OUT"
