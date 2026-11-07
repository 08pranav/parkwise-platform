# Demo tooling

Playwright scripts that drive the **live** site (`https://parkwise-alpha.vercel.app` by default).

```sh
cd demo && npm install && npx playwright install chromium
node discover.mjs [role]     # Phase 1: list what each screen exposes (see FIELD_MAP.md)
node screenshots.mjs         # screenshots of the main screens of every role into ../docs/screenshots/
```

`lib.mjs` has the shared helpers: accessibility-tree activation, a visible cursor, subtitle bar, `tap`, `typeInto`,
`scroll`. Raw recordings and videos are git-ignored.

Status: discovery and screenshots are done. The full narrated video (title card, all roles, 1080p composite,
highlight, square and vertical cuts, GIF) has **not** been recorded yet.
