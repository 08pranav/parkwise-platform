import { newSession, openApp, tryAs, semanticDump, wait, DESKTOP, PHONE } from './lib.mjs';
import fs from 'node:fs';

const apps = [
  { role: 'super-admin', path: '/super-admin/', vp: DESKTOP },
  { role: 'admin', path: '/admin/', vp: DESKTOP },
  { role: 'owner', path: '/owner/', vp: PHONE },
  { role: 'guard', path: '/guard/', vp: PHONE },
  { role: 'user', path: '/user/', vp: PHONE },
];
const only = process.argv[2];
for (const app of apps.filter((a) => !only || a.role === only)) {
  const { browser, page } = await newSession({ viewport: app.vp });
  await openApp(page, app.path);
  await tryAs(page, app.vp);
  const nodes = await semanticDump(page);
  await page.screenshot({ path: `out/discover-${app.role}.png` });
  fs.mkdirSync('out', { recursive: true });
  console.log(`\n## ${app.role}  url=${page.url().replace(/^https?:\/\/[^/]+/, '')}`);
  for (const n of nodes.filter((n) => ['button','textbox','link','tab','checkbox','switch','menuitem'].includes(n.role)).slice(0, 30)) console.log(`  [${n.role || '-'}] "${n.label.replace(/\n/g, ' | ').slice(0, 50)}" @${n.x},${n.y} ${n.w}x${n.h}`);
  await browser.close();
}
