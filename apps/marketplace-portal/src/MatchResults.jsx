import { useEffect, useState } from "react";
import { getListingMatches } from "./api.js";

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
      <div className="app-header">
        <span className="app-title">Your Matches</span>
        <span className="app-title-ur">آپ کے میچز</span>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {matches === null && !error && <p style={{ color: "var(--color-ink-soft)" }}>Finding matches...</p>}
      {matches && matches.length === 0 && (
        <p style={{ color: "var(--color-ink-soft)" }}>No matches yet -- check back later.</p>
      )}
      {matches &&
        matches.map((m) => (
          <div key={m.id} className="match-card">
            <strong>{m.business_name || "(unnamed business)"}</strong>
            <div className="match-meta">
              {m.match_model.replace("_", " ")} &middot; {m.proximity_label} &middot; score {m.final_score.toFixed(3)}
            </div>
            <div className="match-reason">{m.reason}</div>
          </div>
        ))}

      <button className="btn btn-secondary" style={{ marginTop: 8 }} onClick={onBack}>
        Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
      </button>
    </div>
  );
}
