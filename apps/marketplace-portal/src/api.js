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

// testProfile is OPTIONAL -- {full_name, district, trade_category}, only
// meaningful when the BACKEND's SKIP_ELIGIBILITY_CHECK is on and phone
// doesn't already match a real beneficiary (see auth.py's docstring).
// Harmless to send otherwise; the backend just ignores it. Real
// self-registration doesn't exist in this product -- this is a testing
// convenience standing in for what a loan officer would have entered.
export async function requestOtp(phone, testProfile = {}) {
  const res = await fetch(`${API_BASE}/auth/request-otp`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, ...testProfile }),
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

export async function extractListingText(token, rawText) {
  const res = await fetch(`${API_BASE}/listing/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ raw_text: rawText }),
  });
  return asJson(res);
}

export async function saveListing(token, payload) {
  const res = await fetch(`${API_BASE}/listing`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(payload),
  });
  return asJson(res);
}

export async function getListingMatches(token, listingId) {
  const res = await fetch(`${API_BASE}/listing/${listingId}/matches`, {
    headers: authHeaders(token),
  });
  return asJson(res);
}

export async function dismissMatch(token, matchId, dismissingListingId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ dismissing_listing_id: dismissingListingId }),
  });
  return asJson(res);
}

export async function transcribeAudio(token, audioBlob) {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  const res = await fetch(`${API_BASE}/listing/transcribe`, {
    method: "POST",
    headers: authHeaders(token), // NOT Content-Type -- the browser sets the
    // correct multipart boundary itself when the body is FormData; setting
    // it manually here would omit the boundary and break the upload.
    body: formData,
  });
  return asJson(res);
}

export async function searchListings(token, filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, value);
    }
  });
  const res = await fetch(`${API_BASE}/listings/search?${params.toString()}`, {
    headers: authHeaders(token),
  });
  return asJson(res);
}
