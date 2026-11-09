// Small API helpers used by the recorder for the steps a phone cannot do (camera, waiting for time to pass).
import { API } from './lib.mjs';
export async function call(path, { method = 'GET', token, body } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  try { return { status: res.status, json: JSON.parse(text) }; } catch { return { status: res.status, json: text }; }
}
export async function login(role) {
  const r = await call('/api/v1/auth/login/', { method: 'POST', body: { email: `${role}@parkwise.demo`, password: 'Demo@12345' } });
  return r.json.access;
}
export const resetDemo = () => call('/api/v1/admin/reset-demo/', { method: 'POST', token: process.env.DEMO_RESET_TOKEN });
