// Scenes: sign-in screen, slot owner, society admin (phone-sized) and super admin (desktop).
import fs from 'node:fs';
import { newSession, openApp, tryAs, tap, tapAt, scroll, wait, subtitle, semanticDump, PHONE, DESKTOP } from './lib.mjs';
import { call, login } from './api.mjs';

const only = process.argv[2];
async function record(name, viewport, path, fn) {
  if (only && only !== name) return;
  const s = await newSession({ viewport, record: true, dir: `raw/${name}` });
  try {
    await openApp(s.page, path);
    await fn(s.page, viewport);
  } finally {
    const vid = s.page.video();
    await s.context.close(); await s.browser.close();
    fs.renameSync(await vid.path(), `raw/${name}.webm`);
    console.log('saved', name);
  }
}

await record('login', PHONE, '/user/', async (page, vp) => {
  await subtitle(page, 'Sign in with email and password');
  await wait(page, 2500);
  await tapAt(page, 195, 486, 600);
  await page.keyboard.type('user@parkwise.demo', { delay: 60 });
  await tapAt(page, 195, 554, 600);
  await page.keyboard.type('Demo@12345', { delay: 60 });
  await wait(page, 1000);
  await subtitle(page, 'Passwords are checked on the server and the app gets short-lived tokens');
  await tap(page, 'SIGN IN', { role: 'button', pause: 6000 });
  await subtitle(page, 'Signed in as a resident');
  await wait(page, 3000);
});

await record('owner', PHONE, '/owner/', async (page, vp) => {
  await subtitle(page, 'ParkWise: parking slot owner app');
  await wait(page, 2500);
  await tryAs(page, vp);
  await wait(page, 4000);
  await subtitle(page, 'Owners list their slots, set their own hours and prices, and track earnings');
  await wait(page, 3500);
  await scroll(page, 500, 1500);
  await subtitle(page, 'A new slot waits for the society admin to approve it');
  await wait(page, 3000);
  await scroll(page, -500, 1200);
  await tap(page, 'Add slot', { role: 'button', pause: 3500 });
  await subtitle(page, 'Adding a slot: number, floor, vehicle type, hourly rate, availability windows');
  await wait(page, 4000);
});

await record('admin', PHONE, '/admin/', async (page, vp) => {
  await subtitle(page, 'ParkWise: society admin app');
  await wait(page, 2500);
  await tryAs(page, vp);
  await wait(page, 4000);
  await subtitle(page, 'Occupancy, reservations and a join code residents use to enter the society');
  await wait(page, 3500);
  await scroll(page, 500, 1500); await wait(page, 1500);
  for (const [tab, text] of [
    ['Slots', 'Every slot in the society, with its state and price'],
    ['Guards', 'Guards apply, and the admin approves them'],
    ['Owners', 'Slot owners who offer parking in the society'],
    ['Bookings', 'Every booking, payment status and time window'],
  ]) {
    await tap(page, tab, { role: 'tab', pause: 3500 });
    await subtitle(page, text);
    await wait(page, 2500);
  }
});

await record('super', DESKTOP, '/super-admin/', async (page, vp) => {
  const ut = await login('user');
  const list = (await call('/api/v1/bookings/list/', { token: ut })).json;
  const booking = (list.results ?? list).find((b) => b.status !== 'cancelled');
  await subtitle(page, 'ParkWise: platform super admin (desktop)');
  await wait(page, 2500);
  await tryAs(page, vp);
  await wait(page, 4000);
  await subtitle(page, 'All societies, bookings and revenue across the platform');
  await wait(page, 3500);
  await tap(page, 'Societies', { role: 'tab', pause: 3500 });
  await subtitle(page, 'Societies on the platform, and a form to onboard a new one');
  await wait(page, 3000);
  await tap(page, 'Refunds', { role: 'tab', pause: 3000 });
  await subtitle(page, 'Refunds: look a booking up, then refund its payment through Stripe or Razorpay');
  await tapAt(page, 600, 257, 600);
  await page.keyboard.type(booking.id, { delay: 25 });
  await tapAt(page, 1216, 258, 4000);
  await wait(page, 3000);
  await scroll(page, 700, 1500);
  await subtitle(page, 'Full or partial refund, with a required reason that is kept as an audit record');
  await tapAt(page, 640, 489, 600);
  await page.keyboard.type('Customer request (demo)', { delay: 50 });
  await wait(page, 1200);
  await tapAt(page, 640, 582, 2500);
  await subtitle(page, 'A confirmation step guards against accidental refunds');
  await wait(page, 2500);
  await tapAt(page, 773, 475, 8000);
  await page.screenshot({ path: 'out/super-refund-done.png' });
  await subtitle(page, 'The refund is sent to Stripe, and the booking is cancelled');
  await wait(page, 3500);
  await tapAt(page, 949, 148, 3500);
  await subtitle(page, 'Refund history keeps every attempt: pending, succeeded or failed');
  await wait(page, 3500);
});
