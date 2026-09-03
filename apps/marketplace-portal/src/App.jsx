import { useState } from "react";
import { requestOtp, verifyOtp, getMeContext } from "./api.js";
import ListingWizard from "./ListingWizard.jsx";
import MatchResults from "./MatchResults.jsx";
import Search from "./Search.jsx";

export default function App() {
  // "phone" | "code" | "dashboard" | "createListing" | "matches" | "search"
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
    return <MatchResults token={token} listingId={newListingId} onBack={() => setStep("dashboard")} />;
  }

  if (step === "search") {
    return <Search token={token} onBack={() => setStep("dashboard")} />;
  }

  if (step === "dashboard" && context) {
    return (
      <div className="page">
        <Header />
        <div className="card">
          <h2 className="card-heading" style={{ fontSize: 19 }}>
            {context.full_name}
          </h2>
          <div className="dashboard-row">
            <span className="dashboard-label">District</span>
            <span>{context.district}</span>
          </div>
          <div className="dashboard-row">
            <span className="dashboard-label">Cluster</span>
            <span>{context.cluster_id ?? "not set by staff yet"}</span>
          </div>
          <div className="dashboard-row">
            <span className="dashboard-label">Trade category</span>
            <span>{context.trade_category ?? "none on file"}</span>
          </div>
          <div className="dashboard-row">
            <span className="dashboard-label">Stated purpose</span>
            <span>{context.stated_purpose}</span>
          </div>
        </div>

        {/* Search is available regardless of can_create_listing --
            browsing the marketplace was never conditional on having your
            own listing or being matched to anything. */}
        <button
          className="btn btn-secondary btn-block"
          style={{ marginBottom: 10 }}
          onClick={() => setStep("search")}
        >
          Search the Marketplace <span style={{ fontFamily: "var(--font-ur)", marginLeft: 6 }}>مارکیٹ پلیس تلاش کریں</span>
        </button>

        {context.can_create_listing ? (
          <button className="btn btn-primary btn-block" onClick={() => setStep("createListing")}>
            Create a Listing <span style={{ fontFamily: "var(--font-ur)", marginLeft: 6 }}>فہرست بنائیں</span>
          </button>
        ) : (
          <p style={{ color: "var(--color-ink-soft)", fontSize: 14 }}>
            Your loan isn't for a business, so listing creation isn't available.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="page">
      <Header />

      {step === "phone" && (
        <form className="card" onSubmit={handleRequestOtp}>
          <label className="field-label">
            Phone number <span style={{ fontFamily: "var(--font-ur)", fontWeight: 400 }}>فون نمبر</span>
          </label>
          <input
            className="input"
            type="tel"
            placeholder="+92300..."
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            required
          />
          {error && <div className="error-banner">{error}</div>}
          <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
            {busy ? "..." : "Send code"} <span style={{ fontFamily: "var(--font-ur)" }}>کوڈ بھیجیں</span>
          </button>
        </form>
      )}

      {step === "code" && (
        <form className="card" onSubmit={handleVerifyOtp}>
          <label className="field-label">
            Enter the 6-digit code <span style={{ fontFamily: "var(--font-ur)", fontWeight: 400 }}>کوڈ درج کریں</span>
          </label>
          <input
            className="input"
            type="text"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
          {error && <div className="error-banner">{error}</div>}
          <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
            {busy ? "..." : "Verify"} <span style={{ fontFamily: "var(--font-ur)" }}>تصدیق کریں</span>
          </button>
        </form>
      )}
    </div>
  );
}

function Header() {
  return (
    <div className="app-header">
      <span className="app-title">Al-Khidmat Marketplace</span>
      <span className="app-title-ur">مارکیٹ پلیس</span>
    </div>
  );
}
