// Live smoke test: drives the deployed API like a visitor would, across every role.
//
//   cd scripts && npm install && npx playwright install chromium
//   API_URL=https://... node smoke-live.mjs
//
// Covers: login for all five roles, a booking paid with a real Stripe test card (hosted
// checkout in a headless browser), QR entry, replay rejection, overstay penalty, and a
// refund through the super-admin API. The Razorpay leg creates a real test-mode order and
// confirms the capture with a signed webhook (set RAZORPAY_WEBHOOK_SECRET to enable it).
import crypto from 'node:crypto';
import { chromium } from 'playwright';

const API = (process.env.API_URL ?? 'https://parkwise-api-77gc.onrender.com').replace(/\/$/, '');
const PASSWORD = 'Demo@12345';
let failures = 0;

const log = (ok, name, detail = '') => {
  if (!ok) failures++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  ' + detail : ''}`);
};

async function call(path, { method = 'GET', token, body, raw } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: raw ?? (body ? JSON.stringify(body) : undefined),
  });
  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch { json = text; }
  return { status: res.status, json };
}

async function login(role) {
  const { status, json } = await call('/api/v1/auth/login/', {
    method: 'POST',
    body: { email: `${role}@parkwise.demo`, password: PASSWORD },
  });
  log(status === 200 && json.access, `login as ${role}`);
  return json.access;
}

async function payWithStripeCard(checkoutUrl) {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(checkoutUrl, { waitUntil: 'domcontentloaded' });
    await page.locator('#cardNumber').fill('4242 4242 4242 4242');
    await page.locator('#cardExpiry').fill('12 / 34');
    await page.locator('#cardCvc').fill('123');
    const name = page.locator('#billingName');
    if (await name.count()) await name.fill('Demo Visitor');
    await page.locator('.SubmitButton').click();
    await page.waitForURL((u) => !u.hostname.endsWith('stripe.com'), { timeout: 60000 });
    return page.url();
  } finally {
    await browser.close();
  }
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- health
{
  let res;
  for (let i = 0; i < 12; i++) {
    res = await call('/api/health/').catch(() => ({ status: 0, json: {} }));
    if (res.status === 200) break;
    await wait(10000); // free-tier cold start
  }
  log(res.status === 200 && res.json.database && res.json.redis, 'health: database and redis up', JSON.stringify(res.json));
}

// ---------------------------------------------------------------- all five roles can sign in
const tokens = {};
for (const role of ['user', 'owner', 'admin', 'guard', 'super']) tokens[role] = await login(role);

// ---------------------------------------------------------------- admin and owner views
{
  const dash = await call('/api/v1/admin/dashboard/', { token: tokens.super });
  log(dash.status === 200, 'super admin dashboard loads');
  const sdash = await call('/api/v1/admin/society/dashboard/', { token: tokens.admin });
  log(sdash.status === 200, 'society admin dashboard loads');
  const profile = await call('/api/v1/auth/profile/', { token: tokens.owner });
  const slots = await call(`/api/v1/societies/${profile.json.society}/slots/?owner_id=${profile.json.id}`, { token: tokens.owner });
  const results = slots.json.results ?? slots.json;
  log(results.length >= 2, 'owner sees their own slots', `${results.length} slots`);
  log(results.some((s) => s.approval_status === 'pending'), 'owner has a slot awaiting approval');
}

// ---------------------------------------------------------------- booking, Stripe payment
const profile = (await call('/api/v1/auth/profile/', { token: tokens.user })).json;
const vehicles = (await call('/api/v1/auth/vehicles/', { token: tokens.user })).json;
const car = (vehicles.results ?? vehicles).find((v) => v.vehicle_type === 'car');
const slotList = (await call(`/api/v1/societies/${profile.society}/slots/?slot_type=car`, { token: tokens.user })).json;
const freeSlots = (slotList.results ?? slotList).filter((s) => s.state === 'available');

async function book() {
  const start = new Date(Date.now() + 10 * 60000);
  const end = new Date(start.getTime() + 2 * 3600000);
  for (const slot of freeSlots) {
    const res = await call('/api/v1/bookings/', {
      method: 'POST',
      token: tokens.user,
      body: { slot_id: slot.id, vehicle_id: car.id, start_time: start.toISOString(), end_time: end.toISOString() },
    });
    if (res.status === 201) return res.json;
  }
  return null;
}

const booking = await book();
log(!!booking, 'resident books a slot', booking && `${booking.booking_number}, INR ${booking.amount}, surge x${booking.surge_multiplier}`);

const stripe = await call('/api/v1/payments/initiate/', {
  method: 'POST', token: tokens.user, body: { booking_id: booking.id, gateway: 'stripe' },
});
log(stripe.status === 201 && stripe.json.checkout_url, 'Stripe checkout session created');

const returnedTo = await payWithStripeCard(stripe.json.checkout_url);
log(/checkout=success/.test(returnedTo), 'paid with Stripe test card 4242', returnedTo.split('?')[0]);

const sessionId = stripe.json.stripe_checkout_session_id;
let confirmed;
for (let i = 0; i < 10; i++) {
  confirmed = (await call(`/api/v1/bookings/${booking.id}/`, { token: tokens.user })).json;
  if (confirmed.status === 'confirmed') break;
  await call('/api/v1/payments/verify/', { method: 'POST', token: tokens.user, body: { checkout_session_id: sessionId } });
  await wait(3000);
}
log(confirmed.status === 'confirmed', 'booking is confirmed after payment', confirmed.status);

const qr = await call(`/api/v1/bookings/${booking.id}/qr/`, { token: tokens.user });
log(qr.status === 200, 'QR code is issued for the paid booking');

// ---------------------------------------------------------------- gate: entry, replay, overstay
const superFast = (minutes) => call('/api/v1/admin/demo/fast-forward/', {
  method: 'POST', token: tokens.super, body: { booking_id: booking.id, minutes },
});
log((await superFast(15)).status === 200, 'demo fast-forward: arrive inside the window');
const token = (await call(`/api/v1/bookings/${booking.id}/qr-token/`, { token: tokens.user })).json.qr_token;
log(!!token, 'resident can read the QR code text for manual entry');

const entry = await call('/api/v1/qr/entry/', { method: 'POST', token: tokens.guard, body: { qr_token: token } });
log(entry.status === 200 && entry.json.status === 'entry_granted', 'guard scan: entry granted');
const replay = await call('/api/v1/qr/entry/', { method: 'POST', token: tokens.guard, body: { qr_token: token } });
log(replay.status === 400, 'guard scan: second scan rejected (replay protection)', JSON.stringify(replay.json).slice(0, 90));

log((await superFast(150)).status === 200, 'demo fast-forward: stay past the end time');
const exit = await call('/api/v1/qr/exit/', { method: 'POST', token: tokens.guard, body: { qr_token: token } });
log(exit.status === 200 && exit.json.overstay === true, 'guard scan: exit granted with overstay', exit.json.penalty && `penalty INR ${exit.json.penalty.amount}`);
const penalties = (await call('/api/v1/penalties/', { token: tokens.user })).json;
log((penalties.results ?? penalties).some((p) => p.status === 'unpaid'), 'resident sees the unpaid penalty');

// ---------------------------------------------------------------- refund by the super admin
const lookup = await call(`/api/v1/admin/refunds/lookup/?booking_id=${booking.id}`, { token: tokens.super });
log(lookup.status === 200, 'refund lookup finds the booking and its payment');
const refund = await call('/api/v1/admin/refunds/', {
  method: 'POST', token: tokens.super,
  body: { booking_id: booking.id, refund_amount: confirmed.amount, reason: 'Live smoke test refund' },
});
log(refund.status === 201 || refund.status === 200, 'super admin refunds the Stripe payment (test mode)', JSON.stringify(refund.json).slice(0, 100));
const after = (await call(`/api/v1/bookings/${booking.id}/`, { token: tokens.user })).json;
log(after.status === 'cancelled', 'refunded booking is cancelled', after.status);

// ---------------------------------------------------------------- Razorpay
{
  const second = await book();
  log(!!second, 'resident can book again after the refund');
  const order = await call('/api/v1/payments/initiate/', {
    method: 'POST', token: tokens.user, body: { booking_id: second.id, gateway: 'razorpay' },
  });
  log(order.status === 201 && order.json.razorpay_order_id, 'Razorpay test-mode order created', order.json.razorpay_order_id);
  const secret = process.env.RAZORPAY_WEBHOOK_SECRET;
  if (secret && order.json.razorpay_order_id) {
    const body = JSON.stringify({
      event: 'payment.captured',
      payload: { payment: { entity: { id: `pay_smoke_${Date.now()}`, order_id: order.json.razorpay_order_id } } },
    });
    const signature = crypto.createHmac('sha256', secret).update(body).digest('hex');
    const hook = await fetch(`${API}/api/v1/payments/razorpay/webhook/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Razorpay-Signature': signature, 'X-Razorpay-Event-Id': `smoke-${Date.now()}` },
      body,
    });
    log(hook.status === 200, 'signed Razorpay webhook accepted');
    const bad = await fetch(`${API}/api/v1/payments/razorpay/webhook/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Razorpay-Signature': 'bad' }, body,
    });
    log(bad.status === 400, 'forged Razorpay webhook rejected');
    const b = (await call(`/api/v1/bookings/${second.id}/`, { token: tokens.user })).json;
    log(b.status === 'confirmed', 'booking confirmed by the Razorpay webhook', b.status);
  }
}

// ---------------------------------------------------------------- reset so the demo is clean again
if (process.env.DEMO_RESET_TOKEN) {
  const reset = await call('/api/v1/admin/reset-demo/', {
    method: 'POST', token: process.env.DEMO_RESET_TOKEN,
  });
  log(reset.status === 200, 'demo data reset after the run');
}

console.log(failures ? `\n${failures} check(s) failed` : '\nAll checks passed');
process.exit(failures ? 1 : 0);
