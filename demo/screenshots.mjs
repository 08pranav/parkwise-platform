// Screenshots of the main screens of every role, taken from the live site into ../docs/screenshots/.
import { newSession, openApp, tryAs, tap, typeInto, scroll, wait, DESKTOP, PHONE } from './lib.mjs';
import fs from 'node:fs';

const out = '../docs/screenshots';
fs.mkdirSync(out, { recursive: true });
const shot = async (page, name) => { await wait(page, 1500); await page.screenshot({ path: `${out}/${name}.png` }); console.log('saved', name); };

async function session(role, path, vp) {
  const s = await newSession({ viewport: vp });
  await openApp(s.page, path);
  await tryAs(s.page, vp);
  await wait(s.page, 3000);
  return s;
}

{ // Super admin
  const { browser, page } = await session('super', '/super-admin/', DESKTOP);
  await shot(page, 'super-admin-dashboard');
  await tap(page, 'Societies', { role: 'tab', pause: 3000 });
  await shot(page, 'super-admin-societies');
  await tap(page, 'Refunds', { role: 'tab', pause: 3000 });
  await shot(page, 'super-admin-refunds');
  await browser.close();
}
{ // Society admin
  const { browser, page } = await session('admin', '/admin/', DESKTOP);
  await shot(page, 'admin-dashboard');
  for (const tab of ['Slots', 'Guards', 'Owners', 'Bookings']) {
    await tap(page, tab, { role: 'tab', pause: 3500 });
    await shot(page, `admin-${tab.toLowerCase()}`);
  }
  await browser.close();
}
{ // Owner
  const { browser, page } = await session('owner', '/owner/', PHONE);
  await wait(page, 4000);
  await shot(page, 'owner-slots');
  await browser.close();
}
{ // Guard
  const { browser, page } = await session('guard', '/guard/', PHONE);
  await shot(page, 'guard-home');
  await browser.close();
}
{ // Resident
  const { browser, page } = await session('user', '/user/', PHONE);
  await shot(page, 'user-home');
  await typeInto(page, 'Where do you need parking?', 'Bandra');
  await wait(page, 3500);
  await tap(page, 'Gurunanak Marg', { role: 'button' });
  await tap(page, 'Find Available Parking', { role: 'button', pause: 5000 });
  await scroll(page, 700);
  await shot(page, 'user-search-results');
  await tap(page, 'Lakeview Heights', { role: 'button', pause: 4000 });
  await shot(page, 'user-society-detail');
  await browser.close();
}
