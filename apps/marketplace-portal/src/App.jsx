import { useState } from "react";
import { requestOtp, verifyOtp, getMeContext } from "./api.js";

// NOTE on the Urdu+English requirement: this login screen's labels are
// bilingual (the UI chrome itself), but the FULL "show Urdu and English
// in parallel" requirement is really about listing/match CONTENT --
// product_or_service_en vs product_or_service_original -- which lives on
// screens not built yet in this pass (the 5-card form, match results).
// Keep this front of mind when those get built; nothing here fulfills
// that requirement yet, this is just the login step.

const styles = {
  page: { fontFamily: "system-ui, sans-serif", maxWidth: 400, margin: "60px auto", padding: 20 },
  input: { width: "100%", padding: 10, fontSize: 16, marginBottom: 12, boxSizing: "border-box" },
  button: { width: "100%", padding: 10, fontSize: 16, cursor: "pointer" },
  error: { color: "#b00020", marginBottom: 12 },
  label: { display: "block", marginBottom: 6, fontWeight: 600 },
  urdu: { fontSize: 14, color: "#555", fontWeight: 400 },
};

export default function App() {
  const [step, setStep] = useState("phone"); // "phone" | "code" | "loggedIn"
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [token, setToken] = useState(null);
  const [context, setContext] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

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
      setStep("loggedIn");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (step === "loggedIn" && context) {
    return (
      <div style={styles.page}>
        <h2>Welcome, {context.full_name}</h2>
        <p>District: {context.district}</p>
        <p>Trade category: {context.trade_category ?? "(none on file)"}</p>
        <p>Stated purpose: {context.stated_purpose}</p>
        <p>
          Can create a listing:{" "}
          <strong>{context.can_create_listing ? "yes" : "no"}</strong>
        </p>
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
