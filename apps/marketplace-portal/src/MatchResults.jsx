import { useEffect, useState } from "react";
import { getListingMatches } from "./api.js";
import Header from "./Header.jsx";

export default function MatchResults({ token, listingId, onBack }) {
  const [matches, setMatches] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getListingMatches(token, listingId)
      .then((res) => setMatches(res.matches))
      .catch((err) => setError(err.message));
  }, [token, listingId]);

  return (
    <div className="page">
      <Header subtitle="Your Matches" subtitleUr="آپ کے میچز" />

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
