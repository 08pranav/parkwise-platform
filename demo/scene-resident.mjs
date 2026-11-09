// Scene: resident journey on a phone-sized screen. Login -> search -> book -> Stripe test card -> QR code.
import fs from 'node:fs';
import { injectOverlays, newSession, openApp, tryAs, tap, typeInto, scroll, wait, subtitle, PHONE } from './lib.mjs';
import { call, login } from './api.mjs';

fs.mkdirSync('raw', { recursive: true });
const s = await newSession({ viewport: PHONE, record: true, dir: 'raw/resident' });
const { page } = s;

await openApp(page, '/user/');
await subtitle(page, 'ParkWise: resident app. Sign in, or try the demo account');
await wait(page, 2500);
await tryAs(page, PHONE);
await wait(page, 2500);
await subtitle(page, 'Search for parking near where you are going');
await typeInto(page, 'Where do you need parking?', 'Bandra');
await wait(page, 3500);
await tap(page, 'Gurunanak Marg', { role: 'button' });
await subtitle(page, 'Choose the date, start time and how long you need the slot');
await tap(page, 'Duration', { role: 'button', pause: 1500 });
await tap(page, '2 hours', { role: 'menuitem', pause: 1500 });
await tap(page, 'Find Available Parking', { role: 'button', pause: 5000 });
await subtitle(page, 'Societies with free slots, nearest first');
await scroll(page, 500); await wait(page, 1500);
await tap(page, 'Sea Breeze Residency', { role: 'button', pause: 3500 });
await subtitle(page, 'Pick a slot that is free in your time window');
await tap(page, 'AVAILABLE', { role: 'button', pause: 3500 });
await subtitle(page, 'Choose your vehicle and see the price');
await tap(page, 'MH01DM1001', { role: 'button', pause: 1500 });
await tap(page, 'MH01DM1001', { role: 'menuitem', pause: 1500 });
await tap(page, 'Proceed to Checkout', { role: 'button', pause: 3000 });
await subtitle(page, 'Pay with Stripe or Razorpay (test mode)');
await wait(page, 2000);
await tap(page, 'Stripe', { role: 'button', pause: 1000 });
const findFrame = async (sel, ms = 60000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    for (const f of page.frames()) if (await f.locator(sel).count().catch(() => 0)) return f;
    await wait(page, 500);
  }
  throw new Error(`no frame with ${sel}`);
};
const pay = await findFrame('#cardNumber', 30000).catch(async (e) => { await page.screenshot({ path: 'out/fail.png' }); throw e; });
await subtitle(page, 'Stripe test card 4242 4242 4242 4242');
await pay.locator('#cardNumber').pressSequentially('4242424242424242', { delay: 80 });
await pay.locator('#cardExpiry').pressSequentially('1234', { delay: 80 });
await pay.locator('#cardCvc').pressSequentially('123', { delay: 80 });
const name = pay.locator('#billingName');
if (await name.count()) await name.fill('Demo Visitor');
await wait(page, 1200);
await pay.locator('form').first().evaluate((f) => f.requestSubmit());
await wait(page, 9000);
await injectOverlays(page);
await subtitle(page, 'Payment confirmed. A signed QR code is issued');
await wait(page, 3500);
await tap(page, 'Copy code for manual entry', { role: 'button', pause: 1500 });
await subtitle(page, 'The guard scans it at the gate, or types the code if the camera fails');
await wait(page, 3000);
await scroll(page, 600, 1500); await subtitle(page, 'Booking details: society, slot, time and price'); await wait(page, 2500);
const vid = page.video();
await s.context.close(); await s.browser.close();
fs.renameSync(await vid.path(), 'raw/resident.webm');
console.log('saved raw/resident.webm');
