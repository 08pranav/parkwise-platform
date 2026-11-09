// Title and chapter cards as PNGs (ffmpeg here has no text filter), in the three video shapes.
import fs from 'node:fs';
import { chromium } from 'playwright';

export const CHAPTERS = [
  { id: 'landing', title: 'Meet ParkWise', sub: 'Smart parking for housing societies' },
  { id: 'login', title: 'Sign in', sub: 'Email and password, short-lived tokens' },
  { id: 'resident', title: 'Resident: book, pay, get a QR', sub: 'Search, pick a slot, pay with Stripe, receive a signed QR code' },
  { id: 'guard', title: 'Guard: scan in, scan out', sub: 'Entry checks, replay protection and the overstay penalty' },
  { id: 'owner', title: 'Slot owner', sub: 'List a slot, set hours and price' },
  { id: 'admin', title: 'Society admin', sub: 'Occupancy, guards, owners and bookings' },
  { id: 'super', title: 'Super admin: refunds', sub: 'Platform overview and audited refunds' },
];
export const SHAPES = { wide: [1920, 1080], square: [1080, 1080], tall: [1080, 1920] };

const css = `
  body{margin:0;background:radial-gradient(circle at 30% 20%,#2a2a6a,#0e0e22 70%);color:#fff;
       font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;display:flex;align-items:center;justify-content:center;text-align:center}
  .w{padding:0 8%} h1{font-size:var(--h);margin:0 0 .35em;letter-spacing:-.02em} p{font-size:var(--p);margin:.3em 0;color:#cfd0ff;line-height:1.4}
  .tag{display:inline-block;margin-bottom:1.2em;padding:.35em 1em;border-radius:999px;background:#4f46e5;font-size:var(--t);letter-spacing:.12em}
  small{display:block;margin-top:2.2em;font-size:var(--t);color:#9a9bd0;line-height:1.6}`;
const page = (shape, inner) => {
  const [w, h] = SHAPES[shape];
  const base = Math.min(w, h);
  return `<style>${css} body{width:${w}px;height:${h}px;--h:${Math.round(base * 0.075)}px;--p:${Math.round(base * 0.034)}px;--t:${Math.round(base * 0.024)}px}</style><div class=w>${inner}</div>`;
};

export const CARDS = {
  intro: (s) => page(s, `<div class=tag>PARKWISE</div><h1>Smart parking for housing societies</h1><p>Book a slot, pay, scan in at the gate, scan out.</p><p>Five apps, one backend, live and tested.</p>`),
  outro: (s) => page(s, `<h1>ParkWise</h1><p>Built by Pranav Koradiya, Santo Xavier and Junaid Momin</p><p>SDE interns at Specter Technology and Games Pvt. Ltd., Feb to Jun 2026</p><p>Thank you, Dr. Sanket Jack, for the mentorship</p><small>github.com/08pranav/parkwise-platform<br>Live demo: parkwise-alpha.vercel.app<br>Demo data only. Stripe and Razorpay run in test mode.</small>`),
  ...Object.fromEntries(CHAPTERS.map((c, i) => [c.id, (s) => page(s, `<div class=tag>CHAPTER ${i + 1} OF ${CHAPTERS.length}</div><h1>${c.title}</h1><p>${c.sub}</p>`)])),
};

if (process.argv[1].endsWith('make-cards.mjs')) {
  fs.mkdirSync('cards', { recursive: true });
  const browser = await chromium.launch();
  for (const [shape, [w, h]] of Object.entries(SHAPES)) {
    const p = await browser.newPage({ viewport: { width: w, height: h } });
    for (const [name, html] of Object.entries(CARDS)) {
      await p.setContent(html(shape));
      await p.screenshot({ path: `cards/${name}-${shape}.png` });
    }
  }
  await browser.close();
  console.log('cards done');
}
