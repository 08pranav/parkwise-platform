#!/usr/bin/env bash
# Re-record every scene from clean demo data. Needs ../.env.deploy for the demo reset token.
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ../.env.deploy; set +a
node -e "import('./api.mjs').then(async m => console.log('reset', (await m.resetDemo()).status))"
node scene-landing.mjs
node scene-roles.mjs login
node scene-resident.mjs
node scene-guard.mjs
node scene-roles.mjs owner
node scene-roles.mjs admin
node scene-roles.mjs super
