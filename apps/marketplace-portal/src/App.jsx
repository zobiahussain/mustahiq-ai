import { useState } from "react";
import { requestOtp, verifyOtp, getMeContext } from "./api.js";
import ListingWizard from "./ListingWizard.jsx";
import MatchResults from "./MatchResults.jsx";
import ListingDetail from "./ListingDetail.jsx";
import Chat from "./Chat.jsx";
import Home from "./Home.jsx";
import Header from "./Header.jsx";

export default function App() {
  // "phone" | "code" | "home" | "createListing" | "matches" | "listingDetail" | "chat"
  const [step, setStep] = useState("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  // TESTING ONLY -- see api.js's requestOtp() docstring. Real
  // self-registration doesn't exist in this product; these three fields
  // only do anything when the backend's SKIP_ELIGIBILITY_CHECK is on.
  const [testFullName, setTestFullName] = useState("");
  const [testDistrict, setTestDistrict] = useState("");
  const [testTradeCategory, setTestTradeCategory] = useState("");
  const TRADE_CATEGORIES = [
    "Trading businesses", "Grocery / Karyana", "Tailoring & embroidery",
    "Livestock", "Manufacturing", "Services", "Food",
    "Three-wheeler / rickshaw", "Agriculture", "Freelancing / technology",
    "Handicrafts & Artisan Crafts", "Construction & Home Trades",
    "Beauty & Personal Care", "Repair & Maintenance", "Education & Tutoring",
  ];
  const [token, setToken] = useState(null);
  const [context, setContext] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [newListingId, setNewListingId] = useState(null);
  const [selectedListingId, setSelectedListingId] = useState(null);
  const [activeChat, setActiveChat] = useState(null); // { matchId, otherBusinessName } -- Chat is only ever reached from "matches", so its Back always returns there

  async function handleRequestOtp(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await requestOtp(phone, {
        full_name: testFullName || undefined,
        district: testDistrict || undefined,
        trade_category: testTradeCategory || undefined,
      });
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
      setStep("home");
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
        onBack={() => setStep("home")}
        onSelectListing={(id) => {
          setSelectedListingId(id);
          setStep("listingDetail");
        }}
        onOpenChat={(matchId, otherBusinessName) => {
          setActiveChat({ matchId, otherBusinessName });
          setStep("chat");
        }}
      />
    );
  }

  if (step === "listingDetail") {
    return (
      <ListingDetail
        token={token}
        listingId={selectedListingId}
        onBack={() => setStep("home")}
      />
    );
  }

  if (step === "chat" && activeChat) {
    return (
      <Chat
        token={token}
        matchId={activeChat.matchId}
        otherBusinessName={activeChat.otherBusinessName}
        onBack={() => setStep("matches")}
      />
    );
  }

  if (step === "home" && context) {
    return (
      <Home
        token={token}
        context={context}
        onCreateListing={() => setStep("createListing")}
        onSelectListing={(id) => {
          setSelectedListingId(id);
          setStep("listingDetail");
        }}
      />
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

          {/* TESTING ONLY -- only does anything if the backend's
              SKIP_ELIGIBILITY_CHECK is on and this number is new. Real
              beneficiaries never see or need this; a loan officer already
              entered their details for real. Collapsed by default so it
              doesn't read as a normal signup form. */}
          <details style={{ marginTop: 4, marginBottom: 12 }}>
            <summary style={{ fontSize: 13, color: "var(--color-ink-soft)", cursor: "pointer" }}>
              Testing only: enter a custom profile for a new number
            </summary>
            <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              <input
                className="input"
                type="text"
                placeholder="Full name (optional)"
                value={testFullName}
                onChange={(e) => setTestFullName(e.target.value)}
              />
              <input
                className="input"
                type="text"
                placeholder="District, e.g. Multan (optional)"
                value={testDistrict}
                onChange={(e) => setTestDistrict(e.target.value)}
              />
              <select
                className="input"
                value={testTradeCategory}
                onChange={(e) => setTestTradeCategory(e.target.value)}
              >
                <option value="">Trade category (optional)</option>
                {TRADE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </details>

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
