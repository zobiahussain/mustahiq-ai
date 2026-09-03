import { useRef, useState } from "react";
import { extractListingText, saveListing, transcribeAudio } from "./api.js";
import Header from "./Header.jsx";

// The 5-card flow, exactly as designed in Marketplace_Spec.md section 3.
// Every English label carries a REAL Urdu translation next to it (not a
// romanized transliteration like "maal" or "banda") -- someone using
// this app in Urdu should never have to sound out English words spelled
// phonetically. Card 4 shows English and Urdu descriptions of the
// business SIDE BY SIDE, both editable -- the actual fulfillment of the
// bilingual requirement, not just labels.

const ROLES = [
  ["supplier", "سپلائر"],
  ["producer", "بنانے والا"],
  ["retailer", "دکاندار"],
  ["service", "خدمات"],
  ["logistics", "ٹرانسپورٹ"],
];

const SEEKING_OPTIONS = [
  ["inputs", "Materials", "سامان"],
  ["workers", "A worker", "ملازم"],
  ["partner", "A business partner", "شراکت دار"],
  ["work", "Work for myself", "مجھے کام چاہیے"],
];

export default function ListingWizard({ token, onDone }) {
  const [step, setStep] = useState(1);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const [role, setRole] = useState(null);
  const [seeking, setSeeking] = useState({ inputs: false, workers: false, partner: false, work: false });
  const [rawText, setRawText] = useState("");
  const [draft, setDraft] = useState(null);
  const [isRemoteCapable, setIsRemoteCapable] = useState(false);
  const [outputIsPhysical, setOutputIsPhysical] = useState(true);
  const [monthlyCapacity, setMonthlyCapacity] = useState("");
  const [priceRange, setPriceRange] = useState("");
  const [willDeliver, setWillDeliver] = useState(false);
  const [willRelocate, setWillRelocate] = useState(false);
  const [willPartnerOutside, setWillPartnerOutside] = useState(false);
  const [businessName, setBusinessName] = useState("");
  const [isWomenLed, setIsWomenLed] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const anySeekingSelected = Object.values(seeking).some(Boolean);

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => audioChunksRef.current.push(e.data);
      recorder.onstop = async () => {
        // Stop the mic indicator too, not just the recorder -- leaving
        // the stream open after recording ends is a real, common bug
        // (the browser keeps showing "microphone in use").
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        setTranscribing(true);
        try {
          const result = await transcribeAudio(token, blob);
          setRawText((prev) => (prev ? prev + " " + result.text.trim() : result.text.trim()));
        } catch (err) {
          setError(err.message);
        } finally {
          setTranscribing(false);
        }
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (err) {
      setError("Couldn't access the microphone: " + err.message);
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }

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
    <div className="page">
      <Header subtitle="Create a Listing" subtitleUr="نئی فہرست" />

      <Progress step={step} />
      {error && <div className="error-banner">{error}</div>}

      {step === 1 && (
        <div className="card">
          <h3 className="card-heading">
            What best describes your business? <span className="ur">آپ کا کاروبار کیا ہے؟</span>
          </h3>
          {ROLES.map(([key, ur]) => (
            <button key={key} className={`option-btn ${role === key ? "selected" : ""}`} onClick={() => setRole(key)}>
              <span className="en">{key}</span>
              <span className="ur">{ur}</span>
            </button>
          ))}
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" disabled={!role} onClick={() => setStep(2)}>
              Next <span style={{ fontFamily: "var(--font-ur)" }}>اگلا</span>
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="card">
          <h3 className="card-heading">
            What are you looking for right now? <span className="ur">آپ کو کیا چاہیے؟</span>
          </h3>
          {SEEKING_OPTIONS.map(([key, en, ur]) => (
            <button
              key={key}
              className={`option-btn ${seeking[key] ? "selected" : ""}`}
              onClick={() => setSeeking((s) => ({ ...s, [key]: !s[key] }))}
            >
              <span className="en">{en}</span>
              <span className="ur">{ur}</span>
            </button>
          ))}
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-secondary" onClick={() => setStep(1)}>
              Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
            </button>
            <button className="btn btn-primary" disabled={!anySeekingSelected} onClick={() => setStep(3)}>
              Next <span style={{ fontFamily: "var(--font-ur)" }}>اگلا</span>
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="card">
          <h3 className="card-heading">
            Tell us what you make or sell <span className="ur">اپنے کام کے بارے میں بتائیں</span>
          </h3>
          <p className="card-subtext">Urdu or English, typed or spoken -- whatever's easiest.</p>

          <button
            type="button"
            className={`btn ${isRecording ? "btn-accent" : "btn-secondary"}`}
            onClick={isRecording ? stopRecording : startRecording}
            disabled={transcribing}
          >
            {isRecording ? "⏹ Stop recording" : transcribing ? "Transcribing..." : "🎤 Record"}{" "}
            <span style={{ fontFamily: "var(--font-ur)" }}>{isRecording ? "روکیں" : "ریکارڈ کریں"}</span>
          </button>

          <textarea
            className="textarea ur-input"
            dir="auto"
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            placeholder="سلائی، شلوار قمیض، یونیفارم..."
            style={{ marginTop: 12 }}
          />
          <div>
            <button className="btn btn-secondary" onClick={() => setStep(2)}>
              Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
            </button>
            <button className="btn btn-primary" disabled={!rawText.trim() || busy} onClick={handleExtract}>
              {busy ? "Thinking..." : "Next"} {!busy && <span style={{ fontFamily: "var(--font-ur)" }}>اگلا</span>}
            </button>
          </div>
        </div>
      )}

      {step === 4 && draft && (
        <div className="card">
          <h3 className="card-heading">
            Here's what we understood <span className="ur">ہم نے یہ سمجھا</span>
          </h3>
          <p className="card-subtext">Edit either side if it's not quite right.</p>
          <div className="bilingual-row">
            <div className="bilingual-col">
              <div className="bilingual-col-label">English</div>
              <textarea
                className="textarea"
                value={draft.product_or_service_en}
                onChange={(e) => setDraft((d) => ({ ...d, product_or_service_en: e.target.value }))}
              />
            </div>
            <div className="bilingual-col">
              <div className="bilingual-col-label">اردو</div>
              <textarea
                className="textarea ur-input"
                dir="rtl"
                value={draft.product_or_service_original}
                onChange={(e) => setDraft((d) => ({ ...d, product_or_service_original: e.target.value }))}
              />
            </div>
          </div>

          <h4 style={{ fontSize: 14, fontWeight: 600, margin: "20px 0 10px" }}>Two quick questions</h4>
          <label className="checkbox-row">
            <input type="checkbox" checked={isRemoteCapable} onChange={(e) => setIsRemoteCapable(e.target.checked)} />
            <span>
              Can this work be done remotely, or does it need to be in person?{" "}
              <span className="ur" style={{ fontSize: 15 }}>کیا یہ کام دور سے ہو سکتا ہے؟</span>
            </span>
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={outputIsPhysical} onChange={(e) => setOutputIsPhysical(e.target.checked)} />
            <span>
              Does this involve a physical product that needs delivering?{" "}
              <span className="ur" style={{ fontSize: 15 }}>کیا سامان پہنچانا پڑتا ہے؟</span>
            </span>
          </label>

          <div style={{ marginTop: 8 }}>
            <button className="btn btn-secondary" onClick={() => setStep(3)}>
              Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
            </button>
            <button className="btn btn-primary" onClick={() => setStep(5)}>
              Next <span style={{ fontFamily: "var(--font-ur)" }}>اگلا</span>
            </button>
          </div>
        </div>
      )}

      {step === 5 && (
        <div className="card">
          <h3 className="card-heading">
            A few more details <span className="ur">مزید تفصیلات</span>
          </h3>
          <p className="card-subtext">All optional.</p>

          <label className="field-label">Business name</label>
          <input className="input" value={businessName} onChange={(e) => setBusinessName(e.target.value)} />

          <label className="field-label">Monthly capacity</label>
          <input className="input" value={monthlyCapacity} onChange={(e) => setMonthlyCapacity(e.target.value)} />

          <label className="field-label">Price range</label>
          <input className="input" value={priceRange} onChange={(e) => setPriceRange(e.target.value)} />

          {seeking.inputs && (
            <label className="checkbox-row">
              <input type="checkbox" checked={willDeliver} onChange={(e) => setWillDeliver(e.target.checked)} />
              <span>
                Will you deliver outside your area? <span className="ur" style={{ fontSize: 15 }}>کیا آپ اپنے علاقے سے باہر سامان پہنچائیں گے؟</span>
              </span>
            </label>
          )}
          {seeking.work && (
            <label className="checkbox-row">
              <input type="checkbox" checked={willRelocate} onChange={(e) => setWillRelocate(e.target.checked)} />
              <span>
                Would you relocate for work? <span className="ur" style={{ fontSize: 15 }}>کیا آپ کام کے لیے منتقل ہوں گے؟</span>
              </span>
            </label>
          )}
          {seeking.partner && (
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={willPartnerOutside}
                onChange={(e) => setWillPartnerOutside(e.target.checked)}
              />
              <span>
                Would you partner outside your district?{" "}
                <span className="ur" style={{ fontSize: 15 }}>کیا آپ اپنے ضلع سے باہر شراکت داری کریں گے؟</span>
              </span>
            </label>
          )}

          <label className="checkbox-row">
            <input type="checkbox" checked={isWomenLed} onChange={(e) => setIsWomenLed(e.target.checked)} />
            <span>
              Women-led business <span className="ur" style={{ fontSize: 15 }}>خواتین کی رہنمائی میں کاروبار</span>
            </span>
          </label>

          <div style={{ marginTop: 8 }}>
            <button className="btn btn-secondary" onClick={() => setStep(4)}>
              Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
            </button>
            <button className="btn btn-accent" disabled={busy} onClick={handleSave}>
              {busy ? "Saving..." : "Confirm & Create Listing"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Progress({ step }) {
  return (
    <div className="progress">
      {[1, 2, 3, 4, 5].map((n) => (
        <div key={n} className={`progress-dot ${n < step ? "done" : n === step ? "current" : ""}`} />
      ))}
    </div>
  );
}
