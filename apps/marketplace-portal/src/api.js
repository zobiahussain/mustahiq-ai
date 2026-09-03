// Thin wrapper around the real API -- every function here is one fetch
// call, matching one endpoint in services/api/main.py. No business logic
// lives here, same rule as main.py itself: the logic already lives in,
// and was already tested in, packages/marketplace.

// VITE_API_BASE is set in .env.local for local dev, and as a real
// environment variable in Vercel's project settings once deployed --
// pointing at the Render URL. Falls back to localhost so `npm run dev`
// keeps working with zero setup for anyone who hasn't configured it yet.
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function asJson(response) {
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || `request failed (${response.status})`);
  }
  return body;
}

export async function requestOtp(phone) {
  const res = await fetch(`${API_BASE}/auth/request-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone }),
  });
  return asJson(res);
}

export async function verifyOtp(phone, code) {
  const res = await fetch(`${API_BASE}/auth/verify-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, code }),
  });
  return asJson(res);
}

export async function getMeContext(token) {
  const res = await fetch(`${API_BASE}/me/context`, {
    headers: authHeaders(token),
  });
  return asJson(res);
}
