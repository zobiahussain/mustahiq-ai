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

// Voice-first path, added 5 Sep 2026 -- one recording/typed description
// in, a FULL listing draft back (role, seeking flags, description,
// skills, business name, ...). Deliberately does NOT include
// is_remote_capable/output_is_physical/travel flags -- see
// create_listing.py:draft_full_listing_from_speech()'s docstring for
// why those stay a mandatory explicit tap on the review screen, never
// drafted by the model.
export async function draftListing(token, rawText) {
  const res = await fetch(`${API_BASE}/listing/draft`, {
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

export async function getListingDetail(token, listingId) {
  const res = await fetch(`${API_BASE}/listing/${listingId}`, {
    headers: authHeaders(token),
  });
  return asJson(res);
}

export async function uploadListingPhoto(token, listingId, fileBlob) {
  const formData = new FormData();
  formData.append("photo", fileBlob, fileBlob.name || "photo.jpg");
  const res = await fetch(`${API_BASE}/listing/${listingId}/photos`, {
    method: "POST",
    headers: authHeaders(token), // no Content-Type -- see transcribeAudio()'s note, same reason
    body: formData,
  });
  return asJson(res);
}

export async function deleteListingPhoto(token, photoId) {
  const res = await fetch(`${API_BASE}/photos/${photoId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  return asJson(res);
}

// Marketplace_Spec.md section 8 -- "a listing carries an availability
// status the person controls." The backend endpoint existed before this
// wrapper did; nothing in the app called it until the listing detail
// page (ListingDetail.jsx) needed a real control for it.
export async function setListingAvailability(token, listingId, availability) {
  const res = await fetch(`${API_BASE}/listing/${listingId}/availability`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ availability }),
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

// Chat, added 5 Sep 2026 -- direct request: "there should be a chat
// within the marketplace." Open the moment a match exists, well before
// either side marks it "connected" -- see messaging.py's docstring for
// the full two-stage reasoning.
export async function sendMatchMessage(token, matchId, body) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ body }),
  });
  return asJson(res);
}

export async function getMatchMessages(token, matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/messages`, {
    headers: authHeaders(token),
  });
  return asJson(res);
}

export async function connectMatch(token, matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/connect`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return asJson(res);
}

// Returns {full_name, phone} once connected, or throws (404) before
// that -- see messaging.py:get_contact_info()'s docstring for why this
// is gated behind an explicit "connect" action rather than automatic.
export async function getMatchContact(token, matchId) {
  const res = await fetch(`${API_BASE}/matches/${matchId}/contact`, {
    headers: authHeaders(token),
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
