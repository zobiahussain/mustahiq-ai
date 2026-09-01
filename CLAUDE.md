# Mustahiq AI — Al-Khidmat Beneficiary Matching & Allocation Platform

Hackathon project (Alibaba × GitHub × X). Team of five. This repo covers **my module**, not the whole platform.

> **Big update (29 Aug 2026):** the team delivered a substantially revised doc set —
> the platform pivoted from a beneficiary self-service model to a **staff-operated case
> management system** with a verification/prioritization/allocation pipeline, and the
> marketplace was completely redesigned (no fees at all, replaced by voluntary donations
> + "zakat graduation" tracking). A real SQL schema also shipped. This file has been
> updated to match — see **What Changed** and **Needs Reconciling** below before building
> anything that touches the old model.

---

## THE MOST IMPORTANT RULE: teach, don't just ship

The team are strong engineers but fresh grads. Much of this stack is first-contact:
LlamaIndex, pgvector, RAG, workflow engines, deployment. The point of this project is
**that they can rebuild it alone afterwards.**

So, for everything written here:

1. **Explain before writing.** Say what we're about to build, why this approach and not
   the obvious alternative, and what would break if we did it the other way. Then code.
2. **No black boxes.** If a library does something non-obvious (LlamaIndex chunking,
   pgvector's `<=>` operator, HNSW indexes), explain the mechanism — not just the call.
3. **Name the concept.** Tie each piece to the thing it's an instance of ("this is a
   filtered ANN search", "this is an idempotent event handler") so it transfers.
4. **Flag the learning moments.** When something is a genuinely new concept rather than
   boilerplate, say so explicitly and slow down.
5. **Never silently decide.** Architecture choices get surfaced and agreed, not assumed.
6. **Prefer the version they can debug** over the clever version, unless the clever
   version is meaningfully better — and if so, explain why it wins.

Small mechanical edits (renames, imports, formatting) don't need the treatment. Anything
that introduces a concept does.

---

## What changed in the 29 Aug revision

Not a content tweak — a real pivot. Read this before trusting anything from memory of the
earlier revision:

- **No beneficiary accounts, anywhere on the eligibility side.** Only Al-Khidmat staff
  log in (field officer / department admin / super admin). A field officer enters a
  beneficiary's profile *in conversation*, across a desk. Beneficiaries never see a
  screen.
- **Matching got a whole pipeline, not a single step.** It used to be: match → notify.
  Now it's five stages: **Discovery** (automated, produces suggestions) →
  **Potentially Eligible Pool** (waits for a staff-run assessment cycle) →
  **Verification** (staff confirms real need, can fail and exit the pool) →
  **Prioritization** (bi-weekly, a transparent weighted rubric ranks the *unified* pool
  of verified candidates — direct applicants and AI-identified ones ranked identically) →
  **Human Review & Allocation** (staff approves, funds top-ranked within budget). Full
  detail: [docs/End_to_End_Flows.md](docs/End_to_End_Flows.md).
- **Fairness is now structural, not a convention.** `entry_path` (direct vs.
  ai_identified) is recorded for audit but is schema-enforced to never enter a ranking
  computation — see [docs/End_to_End_Flows.md](docs/End_to_End_Flows.md) Use Case 5–6.
- **Programs can require explicit application.** Microfinance is flagged this way —
  discovery still scores it, but the match is suppressed, never pooled, because a loan is
  a debt nobody should be offered unprompted.
- **The marketplace lost every fee.** No registration fee, no premium ranking, no
  donation-commitment schedule, no grace period. Premium ranking was explicitly
  considered and rejected. Replaced by: an optional voluntary donation once a business is
  established, and "zakat graduation" tracked as a reportable metric. Full spec:
  [docs/Marketplace_Spec.md](docs/Marketplace_Spec.md).
- **The marketplace's 3rd model changed.** "Competitive ranking" (pay to rank above
  competitors) is gone — replaced with **employment** (a business needing a skill matched
  to a beneficiary who has it).
- **No LLM, ever, in the eligibility scoring path.** Confirmed explicitly and repeatedly
  across the new docs: rules + XGBoost only, deterministic, milliseconds, auditable.
  Criteria documents get an LLM pass exactly once, at upload, to draft structured rules —
  a human confirms before they take effect. Full detail:
  [docs/Eligibility_Flow_Explained.md](docs/Eligibility_Flow_Explained.md).
- **A real schema shipped.** `packages/data/schema/al_khidmat_core_schema.sql` (11
  tables) and `al_khidmat_marketplace_schema.sql` (13 tables, now including
  `beneficiary_app_accounts`/`login_otps`/`microfinance_loans`/`marketplace_invitations`)
  — see Needs Reconciling below, since it assumes an embeddings provider we already ruled
  out.
- **Two front ends, two access models — resolved and now consistent everywhere.** Staff
  portal: email + password, staff only. Marketplace app: phone + SMS one-time code,
  beneficiary-facing, no staff at all. Every blanket "beneficiaries never log in"
  statement across the docs has been scoped to the eligibility side specifically — the
  marketplace is the deliberate exception, not a contradiction. See Resolved below.

---

## Needs reconciling — still open

1. **Embeddings dimension conflicts with an already-shared decision.** The delivered SQL
   schema uses `vector(768)` throughout, on the assumption Groq or `nomic-embed-text`
   provides embeddings. We already established Groq has no embeddings endpoint (checked
   directly against their API reference) and had committed to local
   `sentence-transformers` at 384-dim — now pushed to GitHub before this revision landed.
   **This is a real conflict, not a stale-text one** — there's a committed schema behind
   the 768 number now. Cleanest reconciliation: keep local embeddings (still no Groq
   dependency, still free, still fast), but switch the model to a **768-dim** local one
   (`BAAI/bge-base-en-v1.5` or `all-mpnet-base-v2` are the standard picks) so the schema
   needs no migration. Recommending this, not silently doing it — confirm before
   `packages/rag` gets built against either number.
2. **Table counts disagree across every doc.** Architecture.md's diagram says 13, its §5
   prose says "Nine tables" then lists ~24 once marketplace tables are counted, and the
   actual SQL says 11 (core) + 13 (marketplace, after `beneficiary_app_accounts` /
   `login_otps` / `microfinance_loans` / `marketplace_invitations` were added) = 24. Not
   load-bearing, just sloppy — treat the SQL files as ground truth for anything
   structural.

---

## System Overview (whole platform, for context — this repo only implements my slice)

### Major components

1. **Main Platform Portal** (React+Vite, P4, staff-facing) — profile entry, the match
   review worklist, the outreach list, verification, the ranked candidate pool +
   allocation, department view. All staff-operated; a beneficiary never sees this screen.
2. **Marketplace app** (React+Vite, me — folder still named `marketplace-portal`)
   — beneficiary-facing, phone + SMS one-time-code login, conversational listing
   creation, match results, no staff involvement.
3. **API Layer** (FastAPI on Render, P3) — the only thing either app talks to; profile
   CRUD, **two separate auth flows** (staff: Supabase Auth email+password, role-gated;
   marketplace: phone + SMS OTP), exposes matching + workflow results.
4. **Discovery Engine** — hard-rule elimination (plain Python) + XGBoost confidence
   scoring. Suggestions only, never an application, never allocates. P1,
   `packages/eligibility`. Runs alongside, but structurally separate from, the
   **Prioritization Rubric** (bi-weekly, transparent weighted scoring over the *verified*
   candidate pool) — also P1, also `packages/eligibility` now. Neither calls the
   **Marketplace matching** (3 models) — me, `packages/marketplace`.
5. **Shared RAG Layer** (LlamaIndex + pgvector + local embeddings, me) — an **in-process
   Python library**, not a separately deployed service. Imported directly by
   `packages/eligibility`, `packages/nlp_assistant`, `packages/marketplace`, and
   `services/api`. Does **not** participate in eligibility scoring — only answers
   questions and surfaces passages, on demand. Also now explicitly owns the one-off
   criteria-document LLM extraction step (drafts `hard_rules`/`soft_signals` JSON for
   admin confirmation).
6. **Workflow/Trigger Layer** (LlamaIndex Workflows) — 7 event triggers + 2 scheduled
   jobs (bi-weekly ranking cycle; daily marketplace expiry sweep), cross-cutting,
   ownership split across roles (see trigger table in
   [Team_Work_Division.md](docs/Team_Work_Division.md)).
7. **Conversational Assistant** (Groq + shared RAG, P4) — on-demand, staff-facing, not a
   trigger. Answers "does this person qualify for anything else" / "what documents does
   this program need," always with a citation.
8. **Data Layer** (Supabase Postgres + pgvector, schema delivered by P3) — 11 core tables
   + 13 marketplace tables. `beneficiary_profiles` carries **no embedding** — purely
   structured. See `packages/data/schema/`.
9. **External: Groq API** — generation only (chat completions, JSON-mode). Not
   embeddings — see Needs Reconciling #1.

### Data flow — the five-stage pipeline plus the marketplace's separate flow

**A. Eligibility side (staff-mediated, five stages):**
profile entered by staff → Discovery scores against every active program (rules
eliminate, XGBoost ranks confidence) → suggestion lands in staff's review worklist →
staff pools it → **Potentially Eligible Pool** (not contacted yet, waits for that
program's assessment cycle) → staff verifies real need during that cycle (can fail and
exit) → verified candidates join the **Unified Candidate Pool** alongside direct
applicants, indistinguishable → bi-weekly, a transparent rubric ranks the whole pool by
verified need → staff reviews and allocates within budget → unfunded candidates roll over
without reapplying.

**B. Re-scan flow** ("day one, day five" pattern, same principle as before): a new or
changed program re-scans *every* existing beneficiary (triggers 5/6), not just new
registrations.

**C. Marketplace (separate module, no staff, no fees):** beneficiary receives a
microfinance loan → later, on their own, opens the app → conversational assistant
structures a listing from voice/text → matching runs automatically against the whole
pool → both parties notified by SMS/email → they connect themselves. A daily sweep
expires unanswered matches (7 days) and unconfirmed listings (6 months).

### System dependency graph

```
Data Engineering (schema)              delivered — packages/data/schema/
  -> Shared RAG (me)                   ships second — Eligibility, Assistant, Marketplace depend on it
       -> Eligibility/Discovery (P1)  --\
       -> Marketplace (me)             --+-> Backend/API (P3) -> both apps (P4, me)
  -> Dedup (P3)                          depends only on schema, not RAG
```

### APIs — mostly undefined (biggest concrete gap, unchanged by this revision)

Architecture.md names exactly **one** endpoint: `POST /profile`. No full endpoint list, no
request/response schemas, no error contract exists anywhere yet. Every other role's
build-in-parallel plan assumes this contract exists — see Open Questions.

### Implementation constraints (whole system, from SRS §7–8)

- Free tier only, no GPU, no paid infra (SRS 7.1).
- English only — multilingual is future work (SRS 7.2).
- Every recommendation/match needs a plain-language reason + traceable source chunk
  (SRS 7.3).
- **Fairness is structural**: `entry_path` recorded for audit, never usable in a ranking
  computation — enforced at the schema/rubric-validation level, not just by convention
  (SRS 7.4).
- Every ranking must be explainable to a factor-by-factor level; each ranking cycle
  snapshots the weights used (SRS 7.4).
- Only staff authenticate; no beneficiary login/password reset/account recovery anywhere
  on the eligibility side (SRS 7.5).
- No row-level security at hackathon scale; named as future production hardening (SRS
  7.5).
- **No training on real beneficiary data** — XGBoost trains on synthetic data for the
  hackathon; in production, `verifications` outcomes become real training labels as the
  platform is used (SRS 7.5, Eligibility_Flow_Explained §3).
- Never auto-enroll; departments decide (SRS §8, Architecture §8).
- **The platform never contacts a beneficiary directly** — every match is staff-reviewed
  first (Architecture §8).
- Microfinance (and any program flagged `requires_explicit_application`) is never offered
  proactively — a loan is a debt (SRS §5.3).
- **No fees anywhere in the marketplace** — no registration fee, no premium ranking, no
  claim on business earnings; only a voluntary, no-schedule donation (Marketplace_Spec
  §1, §10).
- No scraping — retrieval only over uploaded/mock docs (SRS §8, Architecture §8).
- **No LLM/retrieval in the eligibility scoring loop** — deterministic only, for
  auditability (Eligibility_Flow_Explained §7).
- Render free tier sleeps + cold-starts; Groq free tier is rate-limited per minute — the
  top two demo risks named in Team_Work_Division §8.

---

## My scope ("You" in the team docs — Person 2)

**Owned end-to-end:**
- **Shared RAG layer** — pgvector tables, LlamaIndex retrieval pipeline, Groq client
  wrapper (generation only), local embedding wrapper. *Two other roles build against
  this.* Highest-priority, must be stable day one. **New:** also owns the one-off
  criteria-document LLM extraction (hard_rules/soft_signals JSON, admin-confirmed) and
  its chunking+embedding into `program_criteria`.
- **Marketplace module** — 3 business models, now:
  1. Supply-chain pairing (supplier ↔ end-product business)
  2. Employment (business needing a skill ↔ beneficiary who has it) — **replaces the old
     "competitive ranking" model**
  3. Joint-venture formation (complementary skills → new business)
  Plus logistics (rickshaw/three-wheeler operators) as a participant role. Matching:
  complementary-role filter → distance-eligibility filter → vector similarity → proximity
  re-weighting (same cluster ×1.00 / adjacent district ×0.85 / same province ×0.70 /
  elsewhere ×0.50). The distance-eligibility step is gated by **two independent flags**
  on a listing, not one — `is_remote_capable` (does the *work* need someone physically
  present — skips relocate/partner-outside-district checks) and `output_is_physical`
  (does a *good* need transporting — skips the deliver-outside-area check). A remote
  consultant who ships physical sample kits is remote-capable but still has a physical
  output; each gate stays ×1.00 in proximity weighting independently. This
  automatic-match pipeline is distinct from **search**, which a beneficiary runs
  themselves and which applies none of these filters — search is intent-driven, the flags
  only constrain what gets pushed unprompted. Full spec:
  [docs/Marketplace_Spec.md](docs/Marketplace_Spec.md).
- **Marketplace signup gate: `microfinance_loans`, not `applications`.** The eligibility
  side's `applications` table tracks candidacy for any programme and can't double as a
  loan record without overloading it. A dedicated table
  (`packages/data/schema/al_khidmat_marketplace_schema.sql`) is the actual gate: a phone
  number only gets an OTP if it matches a `beneficiary_profiles` row, and full app access
  (the listing-creation flow specifically) requires a `microfinance_loans` row with
  `status` `approved`/`disbursed` **and** `trade_category_id` set — eligibility starts at
  approval, not disbursement, since the trade category is already decided by then; no
  reason to make someone wait on a banking delay. `trade_category_id` is populated from a
  **new field this module requires on the loan application** — the loan officer picks a
  category (or "Not a business") at the same moment they record the loan's purpose; this
  doesn't exist in Al-Khidmat's process today and needs saying out loud in the demo.
  `trade_category_id is null` is what excludes a loan that doesn't lead to a business
  (Liberation Loan and similar) — that beneficiary can log in but is never offered listing
  creation. `defaulted` closes the gate AND deactivates any listing they already have
  (schema reference query J) — a reputational fact, not just a future-signup block. On top
  of this, `marketplace_invitations` auto-sends an SMS signup code the moment a qualifying
  loan is recorded — solves "nothing tells the person the app exists," but is a
  convenience only, never required to sign up.
- **API contract, at least for my slice, is now concrete.** Seven endpoints for the
  marketplace app's login + listing-creation flow (`POST /auth/request-otp`,
  `POST /auth/verify-otp`, `GET /me/context`, `POST /listing/transcribe`,
  `POST /listing/extract`, `POST /listing`, plus the internal embed→match→notify step) —
  designed and confirmed 1 Sep 2026. This is real progress on Open Question 1 below, for
  my module specifically; the eligibility-side contract is still someone else's to define.
- **"English only" (SRS 7.2) is about the matching pipeline, not what a beneficiary has
  to speak.** Marketplace_Spec.md already committed to "voice or text, in whatever
  language they speak" — so every listing field a beneficiary can see gets an `_en`
  version (embedded, matched) and an `_original` version (their actual words, shown back
  to them and their match). Written into `store_listings` and Marketplace_Spec.md §3.
- **No fees, no venture lifecycle.** The old registration-fee/grace-period/donation-ledger
  model is **gone entirely** — replaced by an optional voluntary donation with no
  schedule, and "zakat graduation" (mustahiq → donor) tracked as a reportable metric.
- **Marketplace app** — React + Vite, beneficiary-facing, phone + SMS one-time-code
  login (own auth model, resolved — see `beneficiary_app_accounts`/`login_otps` in
  `packages/data/schema/al_khidmat_marketplace_schema.sql`), shared palette/logo/
  typography with the Main Platform Portal.
- **Dummy data** — applicant + store-listing profiles for the demo.
- **Triggers I own (renumbered and re-scoped — do not reuse the old numbers from
  memory):** 7 (listing created/edited → marketplace matching, notify both parties by
  SMS/email), 9 (daily → expire stale marketplace matches after 7 days, expire
  unconfirmed listings after 6 months). The old triggers 4/7/8/9/half-of-3 no longer
  apply as described.

**Not mine:** cross-program discovery + prioritization rubric/XGBoost (P1), Supabase
schema (P3, **delivered**), FastAPI + dedup (CNIC-first, then RapidFuzz) + Render deploy +
staff auth (P3). Marketplace OTP verification (the send-code/check-code mechanics) is
P3's to build against the schema; the app-side login flow that calls it is mine.
NLP/assistant + Main Portal (P4).

**I depend on:** P3's schema (**now real** — `packages/data/schema/`) and P3's deploy.
**Depends on me:** the eligibility engine and the conversational assistant both call my
RAG service. If it slips, two people stall.

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| LLM inference (generation only) | Groq API (Llama / Qwen open-weight) |
| Embeddings | `sentence-transformers`, local, CPU — dimension **unresolved**, see Needs Reconciling #1 |
| DB + vectors | Supabase Postgres + pgvector |
| RAG | LlamaIndex over pgvector |
| Triggers | LlamaIndex Workflows (typed, event-driven steps) |
| API | FastAPI + Pydantic v2 (P3 owns) |
| Auth — staff | Supabase Auth, email + password (P3 owns) |
| Auth — marketplace | Phone + SMS one-time code, no password (P3: schema/OTP; me: app flow) |
| Hosting | Render free tier + Render cron |
| Frontend | React + Vite |

Everything must run on free tiers. No GPU anywhere.

---

## Hard constraints (from the SRS — do not violate)

- **Recommend, never auto-enroll.** Departments make the final call.
- **Never contact a beneficiary directly — eligibility side only.** Staff reviews every
  match first there. The marketplace is the deliberate exception: it notifies both
  parties directly, since introducing two businesses carries no allocation decision.
- **Fairness is structural.** `entry_path` recorded for audit, never used in ranking.
- **No fees in the marketplace, anywhere.** Voluntary donation only.
- **No web scraping.** Retrieval runs only over uploaded/mock documents.
- **No training on real beneficiary data.**
- **No LLM/retrieval in eligibility scoring.** Deterministic rules + XGBoost only.
- **Every match/recommendation shows a plain-language reason**, traceable to a real
  source chunk (`match_records.source_chunk_id`).
- **English only.** Multilingual is a future enhancement.
- **Filter and rank in one SQL query.** Never fetch top-k by vector and filter in Python
  afterwards — that can return nothing usable.

---

## LLM token accounting

Every Groq call goes through **one wrapper I own**. On each call it prints `usage`
(`prompt_tokens`, `completion_tokens`, `total_tokens`), the model, and the call-site to
the **terminal** — nothing persisted, no database, no CSV. Reason: Groq's free tier is
rate-limited per minute and a demo-day 429 kills the presentation, so watching
consumption live during dev matters more than keeping history. If we ever want history,
swap the `print` for an append to a CSV — one line, add later if needed.

Since embeddings run locally, only chat/completion calls touch Groq's rate limit —
assistant replies, JSON-mode profile parsing, and the one-off criteria-extraction call.
Eligibility scoring itself makes **zero** Groq calls, by design (see Needs Reconciling
and Eligibility_Flow_Explained.md) — this significantly lowers rate-limit risk versus the
earlier revision, since bulk re-scan triggers (5, 6) never touch an LLM at all.

---

## Resolved (this revision answered several old open questions)

- **Reason text: templated, not LLM-generated.** Confirmed explicitly and repeatedly —
  no LLM in the scoring loop at all. Match reasons are built from the rule/score
  breakdown. This was open question territory before; now it's just how the system
  works.
- **Auth model: fully specified, both sides.** Eligibility side: Supabase Auth, staff
  only, three roles (field_officer / department_admin / super_admin) gating criteria-edit
  and department visibility. Marketplace: phone number + SMS one-time code, no password —
  the person's number is already on file from their loan application, links to their
  existing `beneficiary_profiles` row via `beneficiary_app_accounts`, and a number change
  is staff-assisted at a facilitation centre rather than self-service.
- **Marketplace Portal is beneficiary-facing, not a staff tool — confirmed, not just my
  read of Marketplace_Spec.** Every blanket "beneficiaries never log in" statement across
  the docs has been rewritten to scope it to the eligibility side; the marketplace is the
  deliberate exception.
- **Notification channel: SMS + email, both parties, no phone calls.** Specified in
  Marketplace_Spec §7.
- **Marketplace model disambiguation: resolved, and simpler than either option I'd been
  weighing.** Not a classifier and not fully separate retrieval paths — a listing
  declares "seeking flags" (inputs / workers / a partner / work) that determine which
  models it participates in, then a shared filter+similarity+proximity pipeline ranks
  within that.
- **Duplicate-found behavior: resolved.** Flagged to a staff queue (`duplicate_flags`,
  status `pending`); staff confirms or dismisses; merging is manual, never automatic.
- **Store listing creation flow: resolved, and different from either of my old
  guesses.** Not auto-created from profile trade info, and not a manual staff-built
  form — a beneficiary creates it themselves later, conversationally, once a loan is
  disbursed. Entirely separate from profile creation.
- **Venture "earning" status: moot.** No fees, no grace period, no earning-status flag at
  all anymore — this concept doesn't exist in the new design.

## Open questions blocking architecture lock

### Needs a whole-team decision

1. **API contract.** Only `POST /profile` is specified anywhere for the eligibility side —
   still needs whole-team agreement before `services/api` and `apps/main-portal` can build
   in parallel. **My own marketplace slice is no longer blocked on this** — see Resolved,
   `POST /auth/request-otp`, `POST /auth/verify-otp`, `GET /me/context`,
   `POST /listing/transcribe`, `POST /listing/extract`, `POST /listing` are locked for the
   app-side login + listing-creation flow specifically.
2. **Embeddings dimension.** See Needs Reconciling #1 above — recommending a 768-dim
   local model to match the delivered schema without a migration, needs confirming.
3. **Trigger execution model — sync or async?** Still unanswered. Registration-time
   discovery scoring plausibly runs inline (it's milliseconds, deterministic). But
   triggers 5/6 re-scan *all* beneficiaries when a program changes — that can't
   reasonably block an admin's HTTP request, and no queue/worker infra is named anywhere
   for a single Render free-tier service.
4. **The seven program domains are still never listed.** SRS §1 still only names four as
   examples. Blocks Data Engineering's synthetic dataset and Eligibility's "consistent
   across all seven domains" requirement.
5. ~~Marketplace Portal: staff tool or beneficiary app?~~ — **resolved**, see Resolved
   above.
6. ~~How does an account-less beneficiary access their own marketplace listing?~~ —
   **resolved**, see Resolved above.

### Mine to decide — surfacing per the "never silently decide" rule, not deciding alone

7. ~~How marketplace matching decides between the 3 business models~~ — **resolved**,
   see Resolved above.
8. ~~Notification channel for trigger 7~~ — **resolved**, see Resolved above.

### Watch item — a risk our own decision introduced

9. **Render memory budget.** Loading `sentence-transformers` into the same free-tier web
   service as FastAPI + scikit-learn + XGBoost may be tight on Render's free-tier RAM
   ceiling — more so if the embedding-dimension reconciliation lands on a larger 768-dim
   model. Mitigation if it bites: lazy-load the embedder as a singleton, or split it into
   its own light process.

### Minor / can defer

10. `consent_flags`/`consent_given` on Beneficiary Profile — schema field exists,
    semantics (what consent, gates what behavior) never defined.
11. **Doc-hygiene:** table counts disagree across Architecture.md and the SQL files (see
    Needs Reconciling #2) — not load-bearing, just worth a cleanup pass sometime.

---

## Repo layout (decided — single monorepo)

```
apps/main-portal/            Person 4 — React + Vite, staff-facing
apps/marketplace-portal/     Me       — React + Vite, beneficiary-facing, phone+OTP login
services/api/                Person 3 — FastAPI, two auth flows, shared by both apps
packages/rag/                Me       — shared RAG layer + criteria extraction (build first, day one)
packages/marketplace/        Me       — 3 business models, matching, no fees
packages/eligibility/        Person 1 — discovery engine + prioritization rubric
packages/dedup/              Person 3 — CNIC-first, then RapidFuzz duplicate detection
packages/data/                Data Eng role — schema (delivered, packages/data/schema/), synthetic data, features
packages/nlp_assistant/       Person 4 — free-text parsing + conversational assistant
workflows/                    Cross-cutting — LlamaIndex Workflow trigger definitions
docs/                          SRS.md, Architecture.md, Team_Work_Division.md, Eligibility_Flow_Explained.md, End_to_End_Flows.md, Marketplace_Spec.md
```

My work lives in `packages/rag/`, `packages/marketplace/`, and `apps/marketplace-portal/`.

---

## Reference docs

- `docs/SRS.md` — requirements, scope boundaries, system flow
- `docs/Architecture.md` — architecture, data model, end-to-end flow, deployment
- `docs/Team_Work_Division.md` — roles, trigger ownership, build order
- `docs/Eligibility_Flow_Explained.md` — where the LLM runs vs. XGBoost vs. rules vs. RAG,
  and why — read this before touching anything in `packages/eligibility` or the criteria
  extraction step in `packages/rag`
- `docs/End_to_End_Flows.md` — all 11 use cases traced step by step, with tables touched
- `docs/Marketplace_Spec.md` — full marketplace module spec; authoritative for
  `packages/marketplace` and `apps/marketplace-portal`
- `packages/data/schema/al_khidmat_core_schema.sql`,
  `packages/data/schema/al_khidmat_marketplace_schema.sql` — the real, delivered schema
