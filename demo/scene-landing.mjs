// Scene: the public landing page, desktop-sized.
import fs from 'node:fs';
import { newSession, injectOverlays, subtitle, scroll, wait, SITE, DESKTOP } from './lib.mjs';
const s = await newSession({ viewport: DESKTOP, record: true, dir: 'raw/landing' });
const { page } = s;
await page.goto(`${SITE}/`, { waitUntil: 'networkidle' });
await injectOverlays(page);
await subtitle(page, 'ParkWise: smart parking for housing societies');
await wait(page, 3500);
for (let i = 0; i < 4; i++) { await scroll(page, 450, 2200); }
await subtitle(page, 'Five apps share one backend: resident, owner, society admin, guard and super admin');
await wait(page, 3500);
const vid = page.video();
await s.context.close(); await s.browser.close();
fs.renameSync(await vid.path(), 'raw/landing.webm');
console.log('saved landing');
