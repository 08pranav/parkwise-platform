// Scene: gate guard on a phone-sized screen. Entry scan, replay rejection, exit with overstay penalty.
// Headless browsers have no camera, so the code is entered with the app's manual-entry dialog.
import fs from 'node:fs';
import { injectOverlays, newSession, openApp, tryAs, tap, tapAt, scroll, wait, subtitle, PHONE } from './lib.mjs';
import { call, login } from './api.mjs';

const ut = await login('user'), st = await login('super');
const list = (await call('/api/v1/bookings/list/', { token: ut })).json;
const booking = (list.results ?? list).find((b) => b.status === 'confirmed');
if (!booking) throw new Error('no confirmed booking: run scene-resident.mjs first');
const token = (await call(`/api/v1/bookings/${booking.id}/qr-token/`, { token: ut })).json.qr_token;
const fastForward = (minutes) => call('/api/v1/admin/demo/fast-forward/', { method: 'POST', token: st, body: { booking_id: booking.id, minutes } });
const toArrive = async () => {
  const b = (await call(`/api/v1/bookings/${booking.id}/`, { token: ut })).json;
  return Math.max(1, Math.ceil((new Date(b.start_time) - Date.now()) / 60000) + 5);
};
const toOverstay = async () => {
  const b = (await call(`/api/v1/bookings/${booking.id}/`, { token: ut })).json;
  return Math.max(1, Math.ceil((new Date(b.end_time) - Date.now()) / 60000) + 10);
};
await fastForward(await toArrive());

const s = await newSession({ viewport: PHONE, record: true, dir: 'raw/guard' });
const { page } = s;
const paste = async () => {
  await page.evaluate((t) => navigator.clipboard.writeText(t), token);
  await page.keyboard.press('ControlOrMeta+V');
  await wait(page, 1200);
};
const shot = (n) => page.screenshot({ path: `out/guard-${n}.png` });

await openApp(page, '/guard/');
await subtitle(page, 'ParkWise: gate guard app');
await wait(page, 2500);
await tryAs(page, PHONE);
await wait(page, 3000);
await subtitle(page, 'The guard scans the resident\'s QR code at the gate');
await tap(page, 'SCAN ENTRY', { role: 'button', pause: 3500 });
await subtitle(page, 'No camera in this browser, so enter the code by hand');
await tap(page, 'Camera not working', { role: 'button', pause: 2000 });
await paste();
await subtitle(page, 'The server checks the signature, the time window and the booking state');
await tap(page, 'Validate', { role: 'button', pause: 4000 });
await shot('entry');
await subtitle(page, 'Entry granted. The booking is now active');
await wait(page, 3500);
await tap(page, 'Scan Another', { role: 'button', pause: 3000 });
await subtitle(page, 'Scanning the same QR again is rejected (replay protection)');
await tap(page, 'Camera not working', { role: 'button', pause: 2000 });
await paste();
await tap(page, 'Validate', { role: 'button', pause: 4000 });
await shot('replay');
await wait(page, 3500);
await tap(page, 'Back to Home', { role: 'button', pause: 3000 });
await subtitle(page, 'Hours later: the car leaves after the booked time (demo clock moved forward)');
await fastForward(await toOverstay());
await wait(page, 2500);
await tap(page, 'SCAN EXIT', { role: 'button', pause: 3500 });
await tap(page, 'Camera not working', { role: 'button', pause: 2000 });
await paste();
await subtitle(page, 'Exit scan: the server works out the overstay penalty');
await tap(page, 'Validate', { role: 'button', pause: 4500 });
await shot('exit');
await wait(page, 2500);
await scroll(page, 450, 1500);
await subtitle(page, 'Overstay: the car stayed past its booked time, so a penalty is created');
await shot('exit-penalty');
await wait(page, 4500);
await s.context.close(); await s.browser.close();
fs.renameSync(await page.video().path(), 'raw/guard.webm');
