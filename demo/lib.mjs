// Helpers for recording the live ParkWise site with Playwright.
// Flutter web draws to a canvas, so we switch on its accessibility tree and drive the
// semantic nodes (they sit exactly over the painted widgets).
import { chromium } from 'playwright';

export const SITE = process.env.SITE ?? 'https://parkwise-alpha.vercel.app';
export const API = process.env.API_URL ?? 'https://parkwise-api-77gc.onrender.com';
export const PHONE = { width: 390, height: 844 };
export const DESKTOP = { width: 1280, height: 720 };
export const wait = (page, ms) => page.waitForTimeout(ms);

export async function newSession({ viewport, record = false, dir = 'raw', colorScheme = 'light' }) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: 1,
    colorScheme,
    permissions: ['clipboard-read', 'clipboard-write'],
    ...(record ? { recordVideo: { dir, size: viewport } } : {}),
  });
  const page = await context.newPage();
  return { browser, context, page };
}

export async function openApp(page, path) {
  await page.goto(`${SITE}${path}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('flt-glass-pane', { state: 'attached', timeout: 60000 });
  await wait(page, 4000);
  await page.evaluate(() => document.querySelector('flt-semantics-placeholder')?.click());
  await wait(page, 1000);
  await injectOverlays(page);
}

export async function injectOverlays(page) {
  await page.evaluate(() => {
    if (!document.getElementById('demo-cursor')) {
      const c = document.createElement('div');
      c.id = 'demo-cursor';
      c.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M5 3L19 12L12 13L9 20L5 3Z" fill="white" stroke="black" stroke-width="1.5" stroke-linejoin="round"/></svg>';
      c.style.cssText = 'position:fixed;z-index:999999;pointer-events:none;width:24px;height:24px;transition:left .08s,top .08s;filter:drop-shadow(1px 1px 2px rgba(0,0,0,.35));left:20px;top:20px';
      document.body.appendChild(c);
      window.addEventListener('pointermove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    }
    if (!document.getElementById('demo-subtitle')) {
      const b = document.createElement('div');
      b.id = 'demo-subtitle';
      b.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:999998;text-align:center;padding:10px 16px;background:rgba(0,0,0,.78);color:#fff;font:500 15px -apple-system,Segoe UI,sans-serif;letter-spacing:.3px;transition:opacity .3s;pointer-events:none;opacity:0';
      document.body.appendChild(b);
    }
  });
}

export async function subtitle(page, text) {
  await page.evaluate((t) => {
    const b = document.getElementById('demo-subtitle');
    if (!b) return;
    b.textContent = t || '';
    b.style.opacity = t ? '1' : '0';
  }, text);
  if (text) await wait(page, 700);
}

export async function glide(page, x, y) {
  await page.mouse.move(x, y, { steps: 12 });
  await wait(page, 250);
}

/** Click a semantic node by its accessible name; moves the visible cursor first. */
export async function tap(page, name, { role, exact = false, pause = 1200, nth = 0 } = {}) {
  const loc = role
    ? page.getByRole(role, { name, exact }).nth(nth)
    : page.locator(`flt-semantics[aria-label*="${name}"], flt-semantics:has-text("${name}")`).nth(nth);
  let box = await loc.boundingBox({ timeout: 3000 }).catch(() => null);
  for (let i = 0; !box && i < 6; i++) {
    await scroll(page, 320);
    box = await loc.boundingBox({ timeout: 1500 }).catch(() => null);
  }
  if (!box) throw new Error(`tap: "${name}" not found`);
  const vh = page.viewportSize().height;
  for (let i = 0; i < 4 && box && box.y + box.height > vh - 100; i++) {
    await scroll(page, Math.max(120, box.y - vh * 0.4));
    box = (await loc.boundingBox({ timeout: 1500 }).catch(() => null)) ?? box;
  }
  await glide(page, box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await wait(page, pause);
}

/** Scroll the Flutter page like a finger or wheel would. */
export async function scroll(page, dy, pause = 700) {
  const vp = page.viewportSize();
  await page.mouse.move(vp.width / 2, vp.height / 2);
  await page.mouse.wheel(0, dy);
  await wait(page, pause);
}

export async function tapAt(page, x, y, pause = 1200) {
  await glide(page, x, y);
  await page.mouse.click(x, y);
  await wait(page, pause);
}

export async function typeInto(page, name, text, { delay = 40 } = {}) {
  const loc = page.getByRole('textbox', { name }).first();
  const box = await loc.boundingBox({ timeout: 8000 }).catch(() => null);
  if (!box) throw new Error(`typeInto: "${name}" not found`);
  await glide(page, box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await wait(page, 400);
  await page.keyboard.press('Control+A');
  await page.keyboard.type(text, { delay });
  await wait(page, 400);
}

/** The "Try as <role>" button in the demo banner (top right, not in the semantic tree). */
export async function tryAs(page, viewport) {
  await tapAt(page, viewport.width - 62, viewport.width < 500 ? 24 : 22, 6000);
}

export async function semanticDump(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('flt-semantics')]
      .map((el) => {
        const r = el.getBoundingClientRect();
        return {
          role: el.getAttribute('role') || '',
          label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 60),
          x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
        };
      })
      .filter((n) => n.label && n.w > 0 && n.h > 0 && n.y < 2000),
  );
}
