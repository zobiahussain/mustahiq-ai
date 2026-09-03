import { useEffect, useState } from "react";
import { getListingMatches } from "./api.js";

const styles = {
  page: { fontFamily: "system-ui, sans-serif", maxWidth: 480, margin: "40px auto", padding: 20 },
  match: { border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 12 },
  score: { fontSize: 12, color: "#777" },
  reason: { marginTop: 8, fontStyle: "italic" },
};

export default function MatchResults({ token, listingId, onBack }) {
  const [matches, setMatches] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getListingMatches(token, listingId)
      .then((res) => setMatches(res.matches))
      .catch((err) => setError(err.message));
  }, [token, listingId]);

  return (
    <div style={styles.page}>
      <h2>Your Listing's Matches</h2>
      {error && <div style={{ color: "#b00020" }}>{error}</div>}
      {matches === null && !error && <p>Finding matches...</p>}
      {matches && matches.length === 0 && <p>No matches yet -- check back later.</p>}
      {matches &&
        matches.map((m) => (
          <div key={m.id} style={styles.match}>
            <strong>{m.business_name || "(unnamed business)"}</strong>
            <div style={styles.score}>
              {m.match_model} -- {m.proximity_label} -- score {m.final_score.toFixed(3)}
            </div>
            <div style={styles.reason}>{m.reason}</div>
          </div>
        ))}
      <button onClick={onBack}>Back</button>
    </div>
  );
}
