import { useState } from "react";
import { searchListings } from "./api.js";

// Marketplace_Spec.md section 5.3: search is deliberately UNFILTERED by
// distance or willingness -- someone here already knows what they want.
// No cluster/district restriction happens anywhere in this screen or the
// query behind it (search.py) -- that's on purpose, not an oversight.

const TRADE_CATEGORIES = [
  "Trading businesses", "Grocery / Karyana", "Tailoring & embroidery", "Livestock",
  "Manufacturing", "Services", "Food", "Three-wheeler / rickshaw", "Agriculture",
  "Freelancing / technology",
];

const ROLES = ["supplier", "producer", "retailer", "service", "logistics"];

export default function Search({ token, onBack }) {
  const [q, setQ] = useState("");
  const [tradeCategory, setTradeCategory] = useState("");
  const [role, setRole] = useState("");
  const [district, setDistrict] = useState("");
  const [isWomenLed, setIsWomenLed] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function runSearch() {
    setError(null);
    setBusy(true);
    try {
      const res = await searchListings(token, {
        q,
        trade_category: tradeCategory,
        role,
        district,
        is_women_led: isWomenLed ? true : undefined,
      });
      setResults(res.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="app-header">
        <span className="app-title">Search the Marketplace</span>
        <span className="app-title-ur">تلاش کریں</span>
      </div>

      <div className="card">
        <label className="field-label">
          What are you looking for? <span style={{ fontFamily: "var(--font-ur)", fontWeight: 400 }}>آپ کیا ڈھونڈ رہے ہیں؟</span>
        </label>
        <input
          className="input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. leather supplier, tailoring..."
        />

        <label className="field-label">Trade category</label>
        <select className="input" value={tradeCategory} onChange={(e) => setTradeCategory(e.target.value)}>
          <option value="">Any</option>
          {TRADE_CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <label className="field-label">Role</label>
        <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">Any</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>

        <label className="field-label">District</label>
        <input className="input" value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="e.g. Lahore" />

        <label className="checkbox-row">
          <input type="checkbox" checked={isWomenLed} onChange={(e) => setIsWomenLed(e.target.checked)} />
          <span>
            Women-led only <span className="ur" style={{ fontSize: 15 }}>خواتین کی رہنمائی میں</span>
          </span>
        </label>

        {error && <div className="error-banner">{error}</div>}
        <button className="btn btn-primary" disabled={busy} onClick={runSearch}>
          {busy ? "Searching..." : "Search"} <span style={{ fontFamily: "var(--font-ur)" }}>تلاش</span>
        </button>
      </div>

      {results !== null && (
        <>
          <p style={{ color: "var(--color-ink-soft)", fontSize: 13 }}>{results.length} result(s)</p>
          {results.map((r) => (
            <div key={r.id} className="match-card">
              <strong>{r.business_name || "(unnamed business)"}</strong>
              <div className="match-meta">
                {r.role} &middot; {r.trade_category || "uncategorised"} &middot; {r.district}
                {r.is_remote_capable ? " · remote-capable" : ""}
              </div>
              <div className="match-reason">{r.product_or_service_original}</div>
            </div>
          ))}
        </>
      )}

      <button className="btn btn-secondary" style={{ marginTop: 8 }} onClick={onBack}>
        Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
      </button>
    </div>
  );
}
