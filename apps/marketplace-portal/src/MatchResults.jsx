import { useEffect, useState } from "react";
import { getListingMatches, dismissMatch } from "./api.js";
import Header from "./Header.jsx";

// Clarity pass, 5 Sep 2026 -- direct feedback: "I'm not able to see the
// matches triggers properly." Two real problems fixed: (1) a raw
// similarity score ("score 0.734") means nothing to someone reading
// this -- the plain-language `reason` text already IS the explanation,
// so the number is dropped, not added to; (2) cards are now clickable,
// same as Home.jsx's browse cards -- you can see the FULL listing
// before deciding whether to act on a match, not just a two-line
// summary.
//
// TERMINOLOGY, changed same day -- direct feedback: "Match/Matches"
// translated into Urdu came out as "میچز," a straight transliteration
// of the English word, not a real Urdu term -- reads as the same word
// twice, and "match" in this cultural context reads as matchmaking
// (rishta), an odd association for a BUSINESS marketplace. Renamed to
// "Opportunities" / "مواقع" (a real, idiomatic Urdu word --
// "کاروباری مواقع" is genuinely how "business opportunities" gets said)
// everywhere this screen shows it to a person. match_model,
// marketplace_matches, find_matches(), etc. all stay exactly as they
// are -- this is a display-copy change only, not a rename of the
// underlying concept or any code.
//
// The match REASON is now shown bilingually, side by side -- same
// "alongside" treatment the listing description review already used,
// not the small inline Urdu tag most short labels get. reasoning.py now
// asks the ONE Groq call for both languages together (reason_en +
// reason_ur), not a second call.

export default function MatchResults({ token, listingId, onBack, onSelectListing, onOpenChat }) {
  const [matches, setMatches] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getListingMatches(token, listingId)
      .then((res) => setMatches(res.matches))
      .catch((err) => setError(err.message));
  }, [token, listingId]);

  async function handleDismiss(e, matchId) {
    e.stopPropagation(); // don't also trigger the card's click-through
    try {
      await dismissMatch(token, matchId, listingId);
      setMatches((prev) => prev.filter((m) => m.id !== matchId));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <Header subtitle="Opportunities for You" subtitleUr="آپ کے لیے مواقع" />

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
        <div className="stagger results-grid">
          <div className="skeleton" />
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      )}

      {matches && matches.length === 0 && (
        <p style={{ color: "var(--color-ink-soft)" }}>
          No opportunities yet -- we'll text you the moment someone new joins that fits.
          <span className="ur" style={{ display: "block", marginTop: 2 }}>
            ابھی کوئی موقع نہیں -- جیسے ہی کوئی موزوں کاروبار شامل ہوگا، ہم آپ کو بتائیں گے۔
          </span>
        </p>
      )}

      {matches && matches.length > 0 && (
        <div className="stagger results-grid">
          {matches.map((m) => (
            // A <div> here, not a <button> -- a "Dismiss" button lives
            // INSIDE this card, and a <button> nested inside another
            // <button> is invalid HTML (browsers handle the click
            // ordering inconsistently). role="button" + tabIndex +
            // onKeyDown keeps it just as keyboard-accessible as a real
            // button would be.
            <div
              key={m.id}
              role="button"
              tabIndex={0}
              className="match-card match-card-clickable"
              onClick={() => onSelectListing?.(m.other_id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelectListing?.(m.other_id);
              }}
            >
              <div className="match-card-name">{m.business_name || "(unnamed business)"}</div>
              <div className="match-meta">
                <span className="tag tag-primary">{m.match_model.replace("_", " ")}</span>
                <span className="tag tag-accent">{m.proximity_label}</span>
              </div>
              <div className="bilingual-row" style={{ marginTop: 10 }}>
                <div className="bilingual-col">
                  <div className="bilingual-col-label">English</div>
                  <p className="match-reason" style={{ margin: 0 }}>{m.reason}</p>
                </div>
                {m.reason_ur && (
                  <div className="bilingual-col">
                    <div className="bilingual-col-label">اردو</div>
                    <p
                      className="match-reason"
                      dir="rtl"
                      style={{ margin: 0, fontFamily: "var(--font-ur)" }}
                    >
                      {m.reason_ur}
                    </p>
                  </div>
                )}
              </div>
              {m.other_involvements?.length > 0 && (
                <div className="match-meta" style={{ marginTop: 6 }}>
                  {m.other_involvements.map((inv) => (
                    <span key={inv.id} className="tag">also: {inv.business_name || inv.role}</span>
                  ))}
                </div>
              )}
              <button
                type="button"
                className="btn btn-primary"
                style={{ marginTop: 10, padding: "6px 14px", fontSize: 13 }}
                onClick={(e) => {
                  e.stopPropagation();
                  onOpenChat?.(m.id, m.business_name);
                }}
              >
                Message <span style={{ fontFamily: "var(--font-ur)" }}>پیغام</span>
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ marginTop: 10, marginRight: 0, padding: "6px 14px", fontSize: 13 }}
                onClick={(e) => handleDismiss(e, m.id)}
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
