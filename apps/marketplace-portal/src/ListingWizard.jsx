import { useRef, useState } from "react";
import { draftListing, saveListing, transcribeAudio } from "./api.js";
import Header from "./Header.jsx";

// VOICE-FIRST, rebuilt 5 Sep 2026 -- replaces the earlier 5-card
// multiple-choice flow. Direct feedback: tapping through 5 screens of
// questions is real friction, especially for someone using an app like
// this for the first time with low literacy -- and once every field
// became a tap, semantic search stopped doing much real work, since
// almost everything could be filtered structurally. Going back to "just
// talk, AI drafts the rest" is what the embedding architecture actually
// needs to be worth having. See create_listing.py's
// draft_full_listing_from_speech() docstring for the full reasoning.
//
// TWO SCREENS NOW, NOT FIVE:
//   1. Record or type -- exactly what card 3 already was.
//   2. Review everything the AI drafted (role, what they're looking
//      for, description, extras) -- all editable -- PLUS two mandatory
//      questions that are NEVER drafted by the AI, asked directly,
//      every time, no default that lets someone skip past them. See
//      the "NEVER AI-DRAFTED" section below for why.

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
  // Separate from `busy` -- added 5 Sep 2026, direct feedback: saving a
  // listing runs match_and_notify() synchronously (find matches, write
  // an LLM-authored bilingual reason for EACH one, persist, notify) --
  // genuinely can take a minute or two, and a disabled button saying
  // "Saving..." reads as frozen/broken for that long. `saving` drives a
  // dedicated waiting screen (below) explaining what's actually
  // happening, instead of leaving the form just sitting there disabled.
  const [saving, setSaving] = useState(false);

  const [rawText, setRawText] = useState("");
  const [draft, setDraft] = useState(null);

  // Editable, seeded from the AI draft once it comes back (see handleDraft)
  const [role, setRole] = useState(null);
  const [seeking, setSeeking] = useState({ inputs: false, workers: false, partner: false, work: false });
  const [businessName, setBusinessName] = useState("");
  const [isWomenLed, setIsWomenLed] = useState(false);
  const [monthlyCapacity, setMonthlyCapacity] = useState("");
  const [priceRange, setPriceRange] = useState("");

  // NEVER AI-DRAFTED -- always start at the same safe default and require
  // an explicit tap, regardless of what card 1's recording said. These
  // are genuine WHERE-clause FILTERS (Marketplace_Spec.md section 5 step
  // 2), not ranking weights -- guessing wrong here doesn't just rank a
  // listing lower, it silently excludes it from an entire class of
  // matches. See draft_full_listing_from_speech()'s docstring.
  const [isRemoteCapable, setIsRemoteCapable] = useState(false);
  const [outputIsPhysical, setOutputIsPhysical] = useState(true);
  const [willDeliver, setWillDeliver] = useState(false);
  const [willRelocate, setWillRelocate] = useState(false);
  const [willPartnerOutside, setWillPartnerOutside] = useState(false);

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

  async function handleDraft() {
    setError(null);
    setBusy(true);
    try {
      const result = await draftListing(token, rawText);
      setDraft(result);
      // Seed the editable fields from the draft -- visible and
      // overridable, never silently trusted.
      setRole(result.role);
      setSeeking({
        inputs: !!result.seeking_inputs,
        workers: !!result.seeking_workers,
        partner: !!result.seeking_partner,
        work: !!result.seeking_work,
      });
      setBusinessName(result.business_name || "");
      setIsWomenLed(!!result.is_women_led);
      setMonthlyCapacity(result.monthly_capacity || "");
      setPriceRange(result.price_range || "");
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    setError(null);
    setSaving(true);
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
      // deliberately no setSaving(false) on the success path -- onDone()
      // navigates away immediately, and leaving `saving` true means this
      // screen doesn't flash back to the editable form for one frame
      // before the parent swaps it out.
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  if (saving) {
    // Dedicated screen, not just a disabled button -- saveListing()
    // triggers match_and_notify() synchronously (find matches, write an
    // LLM reason for EACH one, persist, notify), which can genuinely
    // take a minute or two. Left sitting on a form with a "Saving..."
    // button for that long reads as frozen, not working.
    return (
      <div className="page">
        <Header subtitle="Create a Listing" subtitleUr="نئی فہرست" />
        <div className="card" style={{ textAlign: "center", padding: "40px 24px" }}>
          <div className="stagger" style={{ marginBottom: 20 }}>
            <div className="skeleton" style={{ height: 14, width: "60%", margin: "0 auto 10px" }} />
            <div className="skeleton" style={{ height: 14, width: "45%", margin: "0 auto" }} />
          </div>
          <h3 className="card-heading" style={{ justifyContent: "center" }}>
            Finding suitable businesses for you...
          </h3>
          <p className="ur" style={{ fontFamily: "var(--font-ur)", fontSize: 17, margin: "4px 0 12px" }}>
            آپ کے لیے موزوں کاروبار تلاش کیے جا رہے ہیں...
          </p>
          <p className="card-subtext" style={{ margin: 0 }}>
            We're checking your listing against everyone else on the marketplace and writing a
            plain-language reason for each match -- this can take a minute or two.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Header subtitle="Create a Listing" subtitleUr="نئی فہرست" />

      <div className="progress">
        <div className={`progress-dot ${step > 1 ? "done" : "current"}`} />
        <div className={`progress-dot ${step === 2 ? "current" : ""}`} />
      </div>
      {error && <div className="error-banner">{error}</div>}

      {step === 1 && (
        <div className="card">
          <h3 className="card-heading">
            Tell us about your business <span className="ur">اپنے کاروبار کے بارے میں بتائیں</span>
          </h3>
          <p className="card-subtext">
            Say (or type) what you make or sell, and what you need right now -- materials, a
            worker, a partner, or work for yourself. Whatever comes naturally, in whatever
            language.
          </p>

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
            placeholder="مثلاً: میں سلائی کرتی ہوں، مجھے کپڑا چاہیے..."
            style={{ marginTop: 12 }}
          />
          <div>
            <button className="btn btn-primary" disabled={!rawText.trim() || busy} onClick={handleDraft}>
              {busy ? "Reading what you said..." : "Next"}{" "}
              {!busy && <span style={{ fontFamily: "var(--font-ur)" }}>اگلا</span>}
            </button>
          </div>
        </div>
      )}

      {step === 2 && draft && (
        <>
          <div className="card">
            <h3 className="card-heading">
              Here's what we understood <span className="ur">ہم نے یہ سمجھا</span>
            </h3>
            <p className="card-subtext">Tap to change anything that's not quite right.</p>

            {/* Deliberately NOT "your business" -- direct feedback, 5 Sep
                2026: someone purely seeking employment (seeking_work) has
                a skill or trade, not necessarily "a business" of their
                own -- the earlier wording presumed everyone here runs one.
                This same question serves both cases now, without needing
                to change depending on what's checked below. */}
            <label className="field-label">
              What best describes what you do? <span className="ur" style={{ fontWeight: 400 }}>آپ کیا کرتے ہیں؟</span>
            </label>
            <div className="chip-row">
              {ROLES.map(([key, ur]) => (
                <button
                  key={key}
                  className={`chip ${role === key ? "active" : ""}`}
                  onClick={() => setRole(key)}
                >
                  {key} <span className="ur" style={{ fontSize: 13 }}>{ur}</span>
                </button>
              ))}
            </div>

            <label className="field-label">What are you looking for right now?</label>
            <div className="chip-row">
              {SEEKING_OPTIONS.map(([key, en, ur]) => (
                <button
                  key={key}
                  className={`chip ${seeking[key] ? "active" : ""}`}
                  onClick={() => setSeeking((s) => ({ ...s, [key]: !s[key] }))}
                >
                  {en} <span className="ur" style={{ fontSize: 13 }}>{ur}</span>
                </button>
              ))}
            </div>

            <label className="field-label" style={{ marginTop: 16 }}>Description</label>
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
          </div>

          {/* Visually separated from the AI-drafted content above --
              these two are never guessed, always a direct question. */}
          <div className="card" style={{ borderColor: "var(--color-accent)" }}>
            <h3 className="card-heading">
              Two direct questions <span className="ur">دو سوالات</span>
            </h3>
            <p className="card-subtext">
              We always ask these ourselves -- they decide who can see your listing, so we
              never guess.
            </p>
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

            {seeking.inputs && (
              <label className="checkbox-row">
                <input type="checkbox" checked={willDeliver} onChange={(e) => setWillDeliver(e.target.checked)} />
                <span>
                  Will you deliver outside your area?{" "}
                  <span className="ur" style={{ fontSize: 15 }}>کیا آپ اپنے علاقے سے باہر سامان پہنچائیں گے؟</span>
                </span>
              </label>
            )}
            {seeking.work && (
              <label className="checkbox-row">
                <input type="checkbox" checked={willRelocate} onChange={(e) => setWillRelocate(e.target.checked)} />
                <span>
                  Would you relocate for work?{" "}
                  <span className="ur" style={{ fontSize: 15 }}>کیا آپ کام کے لیے منتقل ہوں گے؟</span>
                </span>
              </label>
            )}
            {seeking.partner && (
              <label className="checkbox-row">
                <input type="checkbox" checked={willPartnerOutside} onChange={(e) => setWillPartnerOutside(e.target.checked)} />
                <span>
                  Would you partner outside your district?{" "}
                  <span className="ur" style={{ fontSize: 15 }}>کیا آپ اپنے ضلع سے باہر شراکت داری کریں گے؟</span>
                </span>
              </label>
            )}
          </div>

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

            <label className="checkbox-row">
              <input type="checkbox" checked={isWomenLed} onChange={(e) => setIsWomenLed(e.target.checked)} />
              <span>
                Women-led business <span className="ur" style={{ fontSize: 15 }}>خواتین کی رہنمائی میں کاروبار</span>
              </span>
            </label>

            {/* Marketplace_Spec.md section 10: must be shown at listing
                creation AND again at introduction (see MatchResults.jsx). */}
            <p style={{ fontSize: 12, color: "var(--color-ink-soft)", marginTop: 4, marginBottom: 12 }}>
              Al-Khidmat introduces businesses to each other -- it does not broker deals. Terms,
              pricing, delivery and any dispute are entirely between the two of you.
              <span className="ur" style={{ display: "block", marginTop: 2 }}>
                الخدمت صرف تعارف کرواتا ہے -- شرائط، قیمت اور معاملات دونوں فریقین کے درمیان ہیں۔
              </span>
            </p>

            <button className="btn btn-secondary" onClick={() => setStep(1)}>
              Back <span style={{ fontFamily: "var(--font-ur)" }}>پیچھے</span>
            </button>
            <button className="btn btn-accent" disabled={!role || !anySeekingSelected} onClick={handleSave}>
              Confirm & Create Listing
            </button>
          </div>
        </>
      )}
    </div>
  );
}
