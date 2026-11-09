# Demo tooling

Playwright scripts that drive the **live** site (`https://parkwise-alpha.vercel.app` by default) and ffmpeg scripts
that turn the recordings into the video, highlight cuts, GIFs and chapter list.

```sh
cd demo && npm install && npx playwright install chromium
node discover.mjs [role]     # list what each screen exposes (see FIELD_MAP.md)
node screenshots.mjs         # screenshots of every role into ../docs/screenshots/

./record-all.sh              # reset demo data, then record every scene into raw/ (needs ../.env.deploy)
node make-cards.mjs          # title and chapter cards (PNG) in three shapes
node assemble.mjs [gifs|highlight|full|all]
```

## Screen shapes

The apps are meant to run on phones, so phone-sized screens are the default:

| Scene | Viewport |
|---|---|
| Sign-in, resident, guard, slot owner, society admin | 390 x 844 (phone) |
| Landing page, super admin | 1280 x 720 (desktop) |

`assemble.mjs` fits both into 16:9 (1920x1080), square (1080x1080) and vertical (1080x1920) canvases; phone clips get a
bezel on a dark background, and the desktop clips fill the wide frame.

## Scenes

| File | What it shows |
|---|---|
| `scene-landing.mjs` | Landing page |
| `scene-roles.mjs login \| owner \| admin \| super` | Sign-in; slot owner; society admin tabs; super admin refund (lookup, confirm, history) |
| `scene-resident.mjs` | Search, 2-hour slot, vehicle, embedded Stripe checkout with the test card, QR code |
| `scene-guard.mjs` | Entry scan, replay rejection, exit scan with overstay penalty |

Two honest shortcuts: a headless browser has no camera, so the guard enters the code with the app's manual-entry
dialog; and the demo-only fast-forward endpoint (`DEMO_MODE` only) moves the booking's clock so arrival and an
overstay can be shown without waiting hours. `api.mjs` has the few API calls the scenes use.

`media-plan.json` lists which segments go into the highlight cut and the GIFs. `lib.mjs` has the shared helpers:
accessibility-tree activation, a visible cursor, subtitle bar, `tap`, `typeInto`, `scroll`.

Raw recordings, cards and encoded videos are git-ignored. The GIFs in `../docs/assets/gifs/` are committed; the full
video and cuts are attached to the GitHub release.
