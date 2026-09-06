import { useEffect, useRef, useState } from "react";
import {
  getListingDetail,
  uploadListingPhoto,
  deleteListingPhoto,
  setListingAvailability,
} from "./api.js";
import Header from "./Header.jsx";

// Added 5 Sep 2026 -- direct request: "I should be able to click on my
// listing... and see their details as well. There should not be just a
// tab." Before this, nothing showed one listing's full picture -- search
// and match results were both list-shaped, truncated rows. This is the
// click-through target for both.

const AVAILABILITY_OPTIONS = [
  ["seeking", "Actively looking", "فعال طور پر تلاش میں"],
  ["open_to_offers", "Open to offers", "پیشکش کے لیے کھلا"],
  ["committed", "Not available right now", "فی الحال دستیاب نہیں"],
];

export default function ListingDetail({ token, listingId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const d = await getListingDetail(token, listingId);
      setDetail(d);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listingId]);

  async function handlePhotoSelected(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadListingPhoto(token, listingId, file);
      await load(); // refresh so the new photo actually shows
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDeletePhoto(photoId) {
    try {
      await deleteListingPhoto(token, photoId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleAvailabilityChange(value) {
    try {
      await setListingAvailability(token, listingId, value);
      setDetail((d) => ({ ...d, availability: value }));
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <Header subtitle="Listing" />
        <div className="stagger">
          <div className="skeleton" />
          <div className="skeleton" />
        </div>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="page">
        <Header subtitle="Listing" />
        <div className="error-banner">{error}</div>
        <button className="btn btn-secondary" onClick={onBack}>
          Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
        </button>
      </div>
    );
  }

  return (
    <div className="page">
      <Header subtitle={detail.business_name || "Listing"} />
      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <div className="match-meta" style={{ marginBottom: 10 }}>
          <span className="tag tag-primary">{detail.role}</span>
          {detail.trade_category && <span className="tag tag-accent">{detail.trade_category}</span>}
          {detail.is_women_led && <span className="tag">women-led</span>}
          <span>{detail.district}</span>
        </div>

        {detail.photos.length > 0 && (
          <div className="photo-gallery">
            {detail.photos.map((p) => (
              <div key={p.id} className="photo-gallery-item">
                <img src={p.url} alt="" />
                {detail.is_owner && (
                  <button
                    type="button"
                    className="photo-delete-btn"
                    onClick={() => handleDeletePhoto(p.id)}
                    aria-label="Delete photo"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {detail.is_owner && detail.photos.length < 6 && (
          <div style={{ marginTop: detail.photos.length > 0 ? 12 : 0, marginBottom: 16 }}>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              style={{ display: "none" }}
              onChange={handlePhotoSelected}
            />
            <button
              type="button"
              className="btn btn-secondary"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? "Uploading..." : "+ Add a photo"}{" "}
              <span style={{ fontFamily: "var(--font-ur)" }}>تصویر شامل کریں</span>
            </button>
          </div>
        )}

        <h4 style={{ fontSize: 14, fontWeight: 600, margin: "4px 0 6px" }}>Description</h4>
        <p style={{ margin: "0 0 4px" }}>{detail.product_or_service_original}</p>
        <p style={{ fontSize: 13, color: "var(--color-ink-soft)", margin: 0 }}>{detail.product_or_service_en}</p>

        {detail.skills_en && (
          <>
            <h4 style={{ fontSize: 14, fontWeight: 600, margin: "16px 0 6px" }}>Skills</h4>
            <p style={{ margin: 0 }}>{detail.skills_en}</p>
          </>
        )}

        {(detail.monthly_capacity || detail.price_range) && (
          <div style={{ marginTop: 16 }}>
            {detail.monthly_capacity && (
              <div className="dashboard-row">
                <span className="dashboard-label">Capacity</span>
                <span>{detail.monthly_capacity}</span>
              </div>
            )}
            {detail.price_range && (
              <div className="dashboard-row">
                <span className="dashboard-label">Price</span>
                <span>{detail.price_range}</span>
              </div>
            )}
          </div>
        )}

        <div className="match-meta" style={{ marginTop: 16 }}>
          {detail.seeking_inputs && <span className="tag">seeking materials</span>}
          {detail.seeking_workers && <span className="tag">hiring</span>}
          {detail.seeking_partner && <span className="tag">seeking a partner</span>}
          {detail.seeking_work && <span className="tag">seeking work</span>}
          {detail.is_remote_capable && <span className="tag">remote-capable</span>}
        </div>

        {/* Marketplace_Spec.md section 9.4 -- "lets someone judge
            availability before asking." */}
        {detail.other_involvements.length > 0 && (
          <>
            <h4 style={{ fontSize: 14, fontWeight: 600, margin: "16px 0 6px" }}>
              Also confirmed involved in <span className="ur" style={{ fontSize: 15 }}>یہاں بھی شامل ہیں</span>
            </h4>
            <div className="match-meta">
              {detail.other_involvements.map((inv) => (
                <span key={inv.id} className="tag">
                  {inv.business_name || inv.role} ({inv.participant_role})
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      {detail.is_owner && (
        <div className="card">
          <h4 className="card-heading" style={{ fontSize: 15 }}>
            Availability <span className="ur">دستیابی</span>
          </h4>
          <p className="card-subtext">
            You control this -- set it to "not available" any time you don't want new matches.
          </p>
          <div className="chip-row">
            {AVAILABILITY_OPTIONS.map(([value, en, ur]) => (
              <button
                key={value}
                className={`chip ${detail.availability === value ? "active" : ""}`}
                onClick={() => handleAvailabilityChange(value)}
              >
                {en} <span className="ur" style={{ fontSize: 13 }}>{ur}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <button className="btn btn-secondary" onClick={onBack}>
        Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
      </button>
    </div>
  );
}
