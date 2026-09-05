import { useEffect, useState } from "react";
import { searchListings } from "./api.js";
import Header from "./Header.jsx";

// Replaces the old "dashboard with two buttons, THEN a separate search
// screen" flow -- direct feedback, 5 Sep 2026: "if I sign up I should
// just land upon some dashboard type something where I'm already seeing
// listings... just like any Shopify store." Landing here now means
// listings are already visible, zero extra taps -- filters narrow down
// from there, same as before (Marketplace_Spec.md section 5.3: search
// is deliberately unfiltered by distance/willingness, someone here
// already knows what they want).
//
// Cards are now CLICKABLE -- another direct gap: "I'm not able to click
// on any listing when I'm browsing and see their details." Clicking
// calls onSelectListing(id), which App.jsx routes to ListingDetail.jsx.

const TRADE_CATEGORIES = [
  "Trading businesses", "Grocery / Karyana", "Tailoring & embroidery", "Livestock",
  "Manufacturing", "Services", "Food", "Three-wheeler / rickshaw", "Agriculture",
  "Freelancing / technology",
];

const ROLES = ["supplier", "producer", "retailer", "service", "logistics"];

export default function Home({ token, context, onCreateListing, onSelectListing }) {
  const [q, setQ] = useState("");
  const [tradeCategory, setTradeCategory] = useState("");
  const [role, setRole] = useState("");
  const [district, setDistrict] = useState("");
  const [isWomenLed, setIsWomenLed] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

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

  // Loads the moment this screen opens, filters empty -- the actual fix:
  // listings are visible on arrival, not after tapping into a separate
  // search screen first.
  useEffect(() => {
    runSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const anyFilterActive = q || tradeCategory || role || district || isWomenLed;

  return (
    <div className="page">
      <Header subtitle={context.full_name} />

      <div style={{ marginBottom: 16 }}>
        <div className="dashboard-row">
          <span className="dashboard-label">District</span>
          <span>{context.district}</span>
        </div>
        <div className="dashboard-row">
          <span className="dashboard-label">Trade category</span>
          <span>{context.trade_category ?? "none on file"}</span>
        </div>
      </div>

      {context.can_create_listing ? (
        <button className="btn btn-primary btn-block" style={{ marginBottom: 20 }} onClick={onCreateListing}>
          + Create a Listing <span style={{ fontFamily: "var(--font-ur)", marginLeft: 6 }}>فہرست بنائیں</span>
        </button>
      ) : (
        <p style={{ color: "var(--color-ink-soft)", fontSize: 14, marginBottom: 20 }}>
          Your loan isn't for a business, so listing creation isn't available -- but you can
          still browse and search everything below.
        </p>
      )}

      <button
        type="button"
        className="btn btn-secondary btn-block"
        style={{ marginBottom: filtersOpen ? 16 : 24 }}
        onClick={() => setFiltersOpen((v) => !v)}
      >
        {filtersOpen ? "Hide filters" : "Filters & search"}{" "}
        <span style={{ fontFamily: "var(--font-ur)" }}>فلٹرز</span>
      </button>

      {filtersOpen && (
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
          <div className="chip-row">
            <button className={`chip ${tradeCategory === "" ? "active" : ""}`} onClick={() => setTradeCategory("")}>
              Any
            </button>
            {TRADE_CATEGORIES.map((c) => (
              <button
                key={c}
                className={`chip ${tradeCategory === c ? "active" : ""}`}
                onClick={() => setTradeCategory(c === tradeCategory ? "" : c)}
              >
                {c}
              </button>
            ))}
          </div>

          <label className="field-label">Role</label>
          <div className="chip-row">
            <button className={`chip ${role === "" ? "active" : ""}`} onClick={() => setRole("")}>
              Any
            </button>
            {ROLES.map((r) => (
              <button
                key={r}
                className={`chip ${role === r ? "active" : ""}`}
                onClick={() => setRole(r === role ? "" : r)}
              >
                {r}
              </button>
            ))}
          </div>

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
            {busy ? "Searching..." : "Apply filters"} <span style={{ fontFamily: "var(--font-ur)" }}>لاگو کریں</span>
          </button>
        </div>
      )}

      {busy && (
        <div className="stagger results-grid">
          <div className="skeleton" />
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      )}

      {results !== null && !busy && (
        <>
          <p style={{ color: "var(--color-ink-soft)", fontSize: 13 }}>
            {anyFilterActive ? `${results.length} result(s)` : `Browsing all listings (${results.length}) -- newest first`}
          </p>
          <div className="stagger results-grid">
            {results.map((r) => (
              <button
                key={r.id}
                type="button"
                className="match-card match-card-clickable"
                onClick={() => onSelectListing(r.id)}
              >
                <div className="match-card-name">{r.business_name || "(unnamed business)"}</div>
                <div className="match-meta">
                  <span className="tag tag-primary">{r.role}</span>
                  {r.trade_category && <span className="tag tag-accent">{r.trade_category}</span>}
                  {r.district}
                  {r.is_remote_capable ? " · remote-capable" : ""}
                </div>
                <div className="match-reason">{r.product_or_service_original}</div>
              </button>
            ))}
          </div>
          {results.length === 0 && (
            <p style={{ color: "var(--color-ink-soft)", fontSize: 14 }}>
              Nothing matches those filters yet -- try clearing one, or check back later as more
              people join.
            </p>
          )}
        </>
      )}
    </div>
  );
}
