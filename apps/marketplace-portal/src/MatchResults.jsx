import { useEffect, useState } from "react";
import { getListingMatches, dismissMatch } from "./api.js";
import Header from "./Header.jsx";

export default function MatchResults({ token, listingId, onBack }) {
  const [matches, setMatches] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getListingMatches(token, listingId)
      .then((res) => setMatches(res.matches))
      .catch((err) => setError(err.message));
  }, [token, listingId]);

  async function handleDismiss(matchId) {
    try {
      await dismissMatch(token, matchId, listingId);
      setMatches((prev) => prev.filter((m) => m.id !== matchId));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <Header subtitle="Your Matches" subtitleUr="آپ کے میچز" />

      {/* Marketplace_Spec.md section 10: this disclaimer must be shown
          at listing creation AND again at introduction, not buried in a
          policy page -- this screen is "at introduction." */}
      <p style={{ fontSize: 12, color: "var(--color-ink-soft)", marginBottom: 16 }}>
        Al-Khidmat introduces businesses to each other -- it does not broker deals. Terms,
        pricing, delivery and any dispute are entirely between the two of you.
        <span className="ur" style={{ display: "block", marginTop: 2 }}>
          الخدمت صرف تعارف کرواتا ہے -- شرائط، قیمت اور معاملات دونوں فریقین کے درمیان ہیں۔
        </span>
      </p>

      {error && <div className="error-banner">{error}</div>}

      {matches === null && !error && (
        <div className="stagger">
          <div className="skeleton" />
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      )}

      {matches && matches.length === 0 && (
        <p style={{ color: "var(--color-ink-soft)" }}>No matches yet -- check back later.</p>
      )}

      {matches && matches.length > 0 && (
        <div className="stagger">
          {matches.map((m) => (
            <div key={m.id} className="match-card">
              <div className="match-card-name">{m.business_name || "(unnamed business)"}</div>
              <div className="match-meta">
                <span className="tag tag-primary">{m.match_model.replace("_", " ")}</span>
                <span className="tag tag-accent">{m.proximity_label}</span>
                score {m.final_score.toFixed(3)}
              </div>
              <div className="match-reason">{m.reason}</div>
              <button
                className="btn btn-secondary"
                style={{ marginTop: 10, marginRight: 0, padding: "6px 14px", fontSize: 13 }}
                onClick={() => handleDismiss(m.id)}
              >
                Dismiss <span style={{ fontFamily: "var(--font-ur)" }}>مسترد کریں</span>
              </button>
            </div>
          ))}
        </div>
      )}

      <button className="btn btn-secondary" style={{ marginTop: 8 }} onClick={onBack}>
        Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
      </button>
    </div>
  );
}
