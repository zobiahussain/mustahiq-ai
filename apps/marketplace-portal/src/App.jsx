import { useState } from "react";
import { requestOtp, verifyOtp, getMeContext } from "./api.js";
import ListingWizard from "./ListingWizard.jsx";
import MatchResults from "./MatchResults.jsx";

// The Urdu+English "shown in parallel" requirement is fulfilled on the
// listing-creation screen (ListingWizard.jsx, step 4) -- that's where
// real content (product_or_service_en / _original) exists to show side
// by side. This file's login labels are just bilingual UI chrome, not
// the requirement itself.

const styles = {
  page: { fontFamily: "system-ui, sans-serif", maxWidth: 400, margin: "60px auto", padding: 20 },
  input: { width: "100%", padding: 10, fontSize: 16, marginBottom: 12, boxSizing: "border-box" },
  button: { width: "100%", padding: 10, fontSize: 16, cursor: "pointer" },
  error: { color: "#b00020", marginBottom: 12 },
  label: { display: "block", marginBottom: 6, fontWeight: 600 },
  urdu: { fontSize: 14, color: "#555", fontWeight: 400 },
};

export default function App() {
  // "phone" | "code" | "dashboard" | "createListing" | "matches"
  const [step, setStep] = useState("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [token, setToken] = useState(null);
  const [context, setContext] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [newListingId, setNewListingId] = useState(null);

  async function handleRequestOtp(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await requestOtp(phone);
      setStep("code");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifyOtp(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await verifyOtp(phone, code);
      setToken(result.token);
      const ctx = await getMeContext(result.token);
      setContext(ctx);
      setStep("dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (step === "createListing") {
    return (
      <ListingWizard
        token={token}
        onDone={(listingId) => {
          setNewListingId(listingId);
          setStep("matches");
        }}
      />
    );
  }

  if (step === "matches") {
    return (
      <MatchResults
        token={token}
        listingId={newListingId}
        onBack={() => setStep("dashboard")}
      />
    );
  }

  if (step === "dashboard" && context) {
    return (
      <div style={styles.page}>
        <h2>Welcome, {context.full_name}</h2>
        <p>District: {context.district}</p>
        <p>Cluster: {context.cluster_id ?? "(not set by staff yet)"}</p>
        <p>Trade category: {context.trade_category ?? "(none on file)"}</p>
        <p>Stated purpose: {context.stated_purpose}</p>
        {context.can_create_listing ? (
          <button style={styles.button} onClick={() => setStep("createListing")}>
            Create a Listing
          </button>
        ) : (
          <p style={{ color: "#777" }}>
            Your loan isn't for a business, so listing creation isn't available.
          </p>
        )}
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <h1>Al-Khidmat Marketplace</h1>

      {step === "phone" && (
        <form onSubmit={handleRequestOtp}>
          <label style={styles.label}>
            Phone number <span style={styles.urdu}>(فون نمبر)</span>
          </label>
          <input
            style={styles.input}
            type="tel"
            placeholder="+92300..."
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            required
          />
          {error && <div style={styles.error}>{error}</div>}
          <button style={styles.button} type="submit" disabled={busy}>
            {busy ? "..." : "Send code / کوڈ بھیجیں"}
          </button>
        </form>
      )}

      {step === "code" && (
        <form onSubmit={handleVerifyOtp}>
          <label style={styles.label}>
            Enter the 6-digit code <span style={styles.urdu}>(کوڈ درج کریں)</span>
          </label>
          <input
            style={styles.input}
            type="text"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
          {error && <div style={styles.error}>{error}</div>}
          <button style={styles.button} type="submit" disabled={busy}>
            {busy ? "..." : "Verify / تصدیق کریں"}
          </button>
        </form>
      )}
    </div>
  );
}
