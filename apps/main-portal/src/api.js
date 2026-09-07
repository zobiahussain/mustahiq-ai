const BASE = (import.meta.env.VITE_STAFF_API_BASE || '').replace(/\/$/, '');
const KEY = 'mustahiq.staff.session';
let session = null;
try { session = JSON.parse(sessionStorage.getItem(KEY)); } catch { /* An unavailable session store simply requires sign-in again. */ }
let refreshing;

export function setSession(value) {
  session = value;
  try { if (value) sessionStorage.setItem(KEY, JSON.stringify(value)); else sessionStorage.removeItem(KEY); } catch { /* Memory-only sessions remain usable. */ }
}
export function hasSession() { return Boolean(session?.access_token); }
function message(body) {
  if (Array.isArray(body.detail)) return body.detail.map(e => `${e.loc.slice(1).join(' ')}: ${e.msg}`).join('; ');
  return typeof body.detail === 'string' ? body.detail : 'The request could not be completed.';
}
export async function api(path, { method = 'GET', body, retry = true } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  let response;
  try {
    response = await fetch(`${BASE}/portal${path}`, { method, signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}) },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
  } catch (error) {
    throw new Error(error.name === 'AbortError' ? 'This request took too long. Refresh the workspace before retrying to check whether it completed.' : 'Cannot reach the staff API. Check that the backend is running, then retry.');
  } finally { clearTimeout(timeout); }
  if (response.status === 401 && retry && session?.refresh_token && path !== '/session/refresh') {
    refreshing ||= api('/session/refresh', { method: 'POST', body: { refresh_token: session.refresh_token }, retry: false }).then(setSession).finally(() => { refreshing = null; });
    await refreshing;
    return api(path, { method, body, retry: false });
  }
  const result = await response.json().catch(() => ({ detail: 'The API returned an unreadable response.' }));
  if (!response.ok) {
    if (response.status === 401 && path !== '/session') { setSession(null); window.dispatchEvent(new Event('staff-session-expired')); }
    throw new Error(message(result));
  }
  return result;
}

export async function streamApi(path, { body, onEvent }) {
  const response = await fetch(`${BASE}/portal${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const result = await response.json().catch(() => ({ detail: 'The API returned an unreadable response.' }));
    throw new Error(message(result));
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line));
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}
