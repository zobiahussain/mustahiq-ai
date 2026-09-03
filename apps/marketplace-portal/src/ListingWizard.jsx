import { useState } from "react";
import { extractListingText, saveListing } from "./api.js";

// The 5-card flow, exactly as designed in Marketplace_Spec.md section 3:
//   1. Role (tap)
//   2. Looking for (multi-select tap) -- sets the seeking_* flags
//   3. What you make/sell (the ONE text box) -> the one LLM call
//   4. Two direct taps, never LLM-touched: is_remote_capable, output_is_physical
//   5. Details -- shown whenever card 2 selected anything; asks only the
//      travel question relevant to what was picked
//
// Card 3's result is shown back for review BEFORE saving anything --
// Urdu (product_or_service_original) and English (product_or_service_en)
// shown side by side, both editable. This is the actual fulfillment of
// "show Urdu and English in parallel" -- the login screen's bilingual
// labels were just UI chrome; THIS is where real listing content needs
// to satisfy that requirement, and does.

const ROLES = ["supplier", "producer", "retailer", "service", "logistics"];

const styles = {
  page: { fontFamily: "system-ui, sans-serif", maxWidth: 480, margin: "40px auto", padding: 20 },
  card: { border: "1px solid #ddd", borderRadius: 8, padding: 20, marginBottom: 16 },
  option: (selected) => ({
    display: "block",
    width: "100%",
    textAlign: "left",
    padding: 12,
    marginBottom: 8,
    border: selected ? "2px solid #1a73e8" : "1px solid #ccc",
    background: selected ? "#eaf1fd" : "#fff",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 15,
  }),
  input: { width: "100%", padding: 10, fontSize: 15, marginBottom: 12, boxSizing: "border-box" },
  textarea: { width: "100%", padding: 10, fontSize: 15, marginBottom: 12, boxSizing: "border-box", minHeight: 80 },
  button: { padding: "10px 20px", fontSize: 15, cursor: "pointer", marginRight: 8 },
  urdu: { fontSize: 14, color: "#555" },
  error: { color: "#b00020", marginBottom: 12 },
  bilingual: { display: "flex", gap: 12, marginBottom: 12 },
  bilingualCol: { flex: 1 },
  colLabel: { fontSize: 12, color: "#777", marginBottom: 4, textTransform: "uppercase" },
};

export default function ListingWizard({ token, onDone }) {
  const [step, setStep] = useState(1);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const [role, setRole] = useState(null);
  const [seeking, setSeeking] = useState({ inputs: false, workers: false, partner: false, work: false });
  const [rawText, setRawText] = useState("");
  const [draft, setDraft] = useState(null); // { product_or_service_en, product_or_service_original, skills_en }
  const [isRemoteCapable, setIsRemoteCapable] = useState(false);
  const [outputIsPhysical, setOutputIsPhysical] = useState(true);
  const [monthlyCapacity, setMonthlyCapacity] = useState("");
  const [priceRange, setPriceRange] = useState("");
  const [willDeliver, setWillDeliver] = useState(false);
  const [willRelocate, setWillRelocate] = useState(false);
  const [willPartnerOutside, setWillPartnerOutside] = useState(false);
  const [businessName, setBusinessName] = useState("");
  const [isWomenLed, setIsWomenLed] = useState(false);

  const anySeekingSelected = Object.values(seeking).some(Boolean);

  async function handleExtract() {
    setError(null);
    setBusy(true);
    try {
      const result = await extractListingText(token, rawText);
      setDraft(result);
      setStep(4);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    setError(null);
    setBusy(true);
    try {
      const result = await saveListing(token, {
        role,
        product_or_service_en: draft.product_or_service_en,
        product_or_service_original: draft.product_or_service_original,
        skills_en: draft.skills_en,
        seeking_inputs: seeking.inputs,
        seeking_workers: seeking.workers,
        seeking_partner: seeking.partner,
        seeking_work: seeking.work,
        is_remote_capable: isRemoteCapable,
        output_is_physical: outputIsPhysical,
        will_deliver_outside_area: willDeliver,
        will_relocate_for_work: willRelocate,
        will_partner_outside_district: willPartnerOutside,
        monthly_capacity: monthlyCapacity || null,
        price_range: priceRange || null,
        business_name: businessName || null,
        is_women_led: isWomenLed,
      });
      onDone(result.listing_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.page}>
      <h2>Create a Listing</h2>
      {error && <div style={styles.error}>{error}</div>}

      {step === 1 && (
        <div style={styles.card}>
          <h3>
            What best describes your business?{" "}
            <span style={styles.urdu}>(آپ کا کاروبار کیا ہے؟)</span>
          </h3>
          {ROLES.map((r) => (
            <button key={r} style={styles.option(role === r)} onClick={() => setRole(r)}>
              {r}
            </button>
          ))}
          <button style={styles.button} disabled={!role} onClick={() => setStep(2)}>
            Next
          </button>
        </div>
      )}

      {step === 2 && (
        <div style={styles.card}>
          <h3>
            What are you looking for right now?{" "}
            <span style={styles.urdu}>(آپ کو کیا چاہیے؟)</span>
          </h3>
          {[
            ["inputs", "Materials / inputs (maal)"],
            ["workers", "A worker (banda)"],
            ["partner", "A business partner (partner)"],
            ["work", "Work for myself (kaam chahiye)"],
          ].map(([key, label]) => (
            <button
              key={key}
              style={styles.option(seeking[key])}
              onClick={() => setSeeking((s) => ({ ...s, [key]: !s[key] }))}
            >
              {label}
            </button>
          ))}
          <div style={{ marginTop: 12 }}>
            <button style={styles.button} onClick={() => setStep(1)}>Back</button>
            <button style={styles.button} disabled={!anySeekingSelected} onClick={() => setStep(3)}>
              Next
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div style={styles.card}>
          <h3>
            Tell us what you make or sell{" "}
            <span style={styles.urdu}>(اپنے کام کے بارے میں بتائیں)</span>
          </h3>
          <p style={{ fontSize: 13, color: "#777" }}>Urdu or English, whatever's easiest.</p>
          <textarea
            style={styles.textarea}
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            placeholder="سلائی، شلوار قمیض، یونیفارم..."
          />
          <div>
            <button style={styles.button} onClick={() => setStep(2)}>Back</button>
            <button style={styles.button} disabled={!rawText.trim() || busy} onClick={handleExtract}>
              {busy ? "Thinking..." : "Next"}
            </button>
          </div>
        </div>
      )}

      {step === 4 && draft && (
        <div style={styles.card}>
          <h3>Here's what we understood -- edit if needed</h3>
          <div style={styles.bilingual}>
            <div style={styles.bilingualCol}>
              <div style={styles.colLabel}>English (matched against)</div>
              <textarea
                style={styles.textarea}
                value={draft.product_or_service_en}
                onChange={(e) => setDraft((d) => ({ ...d, product_or_service_en: e.target.value }))}
              />
            </div>
            <div style={styles.bilingualCol}>
              <div style={styles.colLabel}>اردو (Original)</div>
              <textarea
                style={styles.textarea}
                dir="rtl"
                value={draft.product_or_service_original}
                onChange={(e) => setDraft((d) => ({ ...d, product_or_service_original: e.target.value }))}
              />
            </div>
          </div>

          <h4 style={{ marginTop: 20 }}>Two quick questions</h4>
          <label style={{ display: "block", marginBottom: 8 }}>
            <input type="checkbox" checked={isRemoteCapable} onChange={(e) => setIsRemoteCapable(e.target.checked)} />{" "}
            Can this work be done remotely, or does it need to be in person?
          </label>
          <label style={{ display: "block", marginBottom: 12 }}>
            <input type="checkbox" checked={outputIsPhysical} onChange={(e) => setOutputIsPhysical(e.target.checked)} />{" "}
            Does this involve a physical product that needs delivering?
          </label>

          <div>
            <button style={styles.button} onClick={() => setStep(3)}>Back</button>
            <button style={styles.button} onClick={() => setStep(5)}>Next</button>
          </div>
        </div>
      )}

      {step === 5 && (
        <div style={styles.card}>
          <h3>A few more details (all optional)</h3>
          <label style={{ display: "block", marginBottom: 4 }}>Business name</label>
          <input style={styles.input} value={businessName} onChange={(e) => setBusinessName(e.target.value)} />

          <label style={{ display: "block", marginBottom: 4 }}>Monthly capacity</label>
          <input style={styles.input} value={monthlyCapacity} onChange={(e) => setMonthlyCapacity(e.target.value)} />

          <label style={{ display: "block", marginBottom: 4 }}>Price range</label>
          <input style={styles.input} value={priceRange} onChange={(e) => setPriceRange(e.target.value)} />

          {seeking.inputs && (
            <label style={{ display: "block", marginBottom: 8 }}>
              <input type="checkbox" checked={willDeliver} onChange={(e) => setWillDeliver(e.target.checked)} />{" "}
              Will you deliver outside your area?
            </label>
          )}
          {seeking.work && (
            <label style={{ display: "block", marginBottom: 8 }}>
              <input type="checkbox" checked={willRelocate} onChange={(e) => setWillRelocate(e.target.checked)} />{" "}
              Would you relocate for work?
            </label>
          )}
          {seeking.partner && (
            <label style={{ display: "block", marginBottom: 8 }}>
              <input type="checkbox" checked={willPartnerOutside} onChange={(e) => setWillPartnerOutside(e.target.checked)} />{" "}
              Would you partner outside your district?
            </label>
          )}

          <label style={{ display: "block", marginBottom: 12 }}>
            <input type="checkbox" checked={isWomenLed} onChange={(e) => setIsWomenLed(e.target.checked)} />{" "}
            Women-led business
          </label>

          <div>
            <button style={styles.button} onClick={() => setStep(4)}>Back</button>
            <button style={styles.button} disabled={busy} onClick={handleSave}>
              {busy ? "Saving..." : "Confirm & Create Listing"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
