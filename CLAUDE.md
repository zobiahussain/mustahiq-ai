# Mustahiq AI — Al-Khidmat Beneficiary Matching & Marketplace Platform

Hackathon project (Alibaba × GitHub × X). Team of five. This repo covers **my module**, not the whole platform.

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

## System Overview (whole platform, for context — this repo only implements my slice)

### Major components

1. **Main Platform Portal** (React+Vite, P4) — profile entry, recommendations view, department view.
2. **Marketplace Portal** (React+Vite, me) — store listing creation, match results, alerts.
3. **API Layer** (FastAPI on Render, P3) — the only thing either portal talks to; profile
   CRUD, demo-scope auth, exposes matching + workflow results.
4. **AI Matching Engine** — one box on the architecture diagram, but two independent
   implementations that never call each other, both calling into #5:
   - Eligibility scoring (rules + XGBoost) — P1, `packages/eligibility`
   - Marketplace business matching (3 models) — me, `packages/marketplace`
5. **Shared RAG Layer** (LlamaIndex + pgvector + local embeddings, me) — an **in-process
   Python library**, not a separately deployed service. Imported directly by
   `packages/eligibility`, `packages/nlp_assistant`, `packages/marketplace`, and
   `services/api`. "Stable internal function signature" means a Python function
   signature, not a REST contract.
6. **Workflow/Trigger Layer** (LlamaIndex Workflows) — 8 event triggers + 1 scheduled
   sweep, cross-cutting, ownership split across roles (see trigger table in
   [Team_Work_Division.md](docs/Team_Work_Division.md)).
7. **Conversational Assistant** (Groq + shared RAG, P4) — on-demand, request/response
   only, not a trigger.
8. **Data Layer** (Supabase Postgres + pgvector, schema owned by P3) — beneficiaries,
   programs, listings, matches, donation ledger; embeddings live alongside the rows they
   describe.
9. **External: Groq API** — generation only (chat completions, JSON-mode). Not
   embeddings — see Resolved below.

### Data flow — three repeating shapes

**A. Immediate flow** (registration / profile update / new listing / new program): event
→ workflow layer fires → eligibility scoring + duplicate detection + marketplace matching
run concurrently and independently of each other → results written back with a reason and
`source_chunk_id` → both portals show the result → beneficiary can ask the assistant for
more detail on request.

**B. Re-trigger flow** ("day one, day five" — SRS §11.2): every new event re-checks
against *everything already in the system*, not just new-vs-new. This is why a new
program re-scans all existing beneficiaries (triggers 5/6) and a new listing re-scans the
whole listing pool (trigger 4), instead of only matching against things created after it.

**C. Venture lifecycle** (time-based for its last step, not event-based): listing created,
registration fee recorded → grace period (~6–12mo, no event fires during this — nothing
happens in the system) → **[trigger 9, scheduled cron]** grace period ends → donation
commitment schedule starts → optional premium fee paid → trigger 8 re-ranks.

### System dependency graph

```
Data Engineering (schema)              ships first — everyone depends on it
  -> Shared RAG (me)                   ships second — Eligibility, Assistant, Marketplace depend on it
       -> Eligibility (P1)         --\
       -> Marketplace (me)         ---+-> Backend/API (P3) -> both portals (P4, me)
  -> Dedup (P3)                        depends only on schema, not RAG
```

### APIs — mostly undefined (biggest concrete gap)

Architecture.md names exactly **one** endpoint: `POST /profile`. No full endpoint list, no
request/response schemas, no error contract exists anywhere yet. Every other role's
build-in-parallel plan assumes this contract exists — see Open Questions.

### Implementation constraints (whole system, from SRS §7–8)

- Free tier only, no GPU, no paid infra (SRS 7.1).
- English only — multilingual is future work (SRS 7.2).
- Every recommendation/match needs a plain-language reason + traceable source chunk
  (SRS 7.3).
- No row-level security at hackathon scale; it's named as future production hardening,
  not a current requirement (SRS 7.4).
- **No training on real beneficiary data** — XGBoost trains on Data Engineering's
  *synthetic* dataset, never on data collected through the live app (SRS 7.4).
- Never auto-enroll; departments decide (SRS §8, Architecture §8).
- No live payments — ledger rows only (SRS §8, Architecture §8).
- No scraping — retrieval only over uploaded/mock docs (SRS §8, Architecture §8).
- Render free tier sleeps + cold-starts; Groq free tier is rate-limited per minute — the
  top two demo risks named in Team_Work_Division §8.

---

## My scope ("You" in the team docs — Person 2)

**Owned end-to-end:**
- **Shared RAG layer** — pgvector tables, LlamaIndex retrieval pipeline, Groq client
  wrapper. *Two other roles build against this.* Highest-priority, must be stable day one.
- **Marketplace module** — the 3 business models:
  1. Supply-chain pairing (supplier ↔ end-product business)
  2. Joint-venture formation (complementary skills → new business)
  3. Competitive ranking (premium fee ranks a listing above competitors)
- **Venture lifecycle & fees** — registration fee, grace period, donation commitment,
  premium fee. Recorded in a Donation Ledger; **no live payment processing.**
- **Marketplace Portal** — React + Vite, separate codebase from the Main Platform Portal,
  shared palette/logo/typography.
- **Dummy data** — applicant + store-listing profiles for the demo.
- **Triggers I own:** 4 (listing created/edited → match pool), 7 (match found → notify
  both sides), 8 (premium fee paid → re-rank), 9 (grace period ends → scheduled Render
  cron sweep), and half of 3 (profile updated → create listing if trade info added).

**Not mine:** eligibility scoring/XGBoost (P1), Supabase schema + synthetic datasets (P3),
FastAPI + RapidFuzz dedup + Render deploy (P3), NLP/assistant + Main Portal (P4).

**I depend on:** P3's schema (trade/business fields, vector columns) and P3's deploy.
**Depends on me:** the eligibility engine and the conversational assistant both call my
RAG service. If it slips, two people stall.

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| LLM inference (generation only) | Groq API (Llama / Qwen open-weight) |
| Embeddings | `sentence-transformers`, local, CPU — `BAAI/bge-small-en-v1.5` (384-dim) |
| DB + vectors | Supabase Postgres + pgvector |
| RAG | LlamaIndex over pgvector |
| Triggers | LlamaIndex Workflows (typed, event-driven steps) |
| API | FastAPI + Pydantic v2 (P3 owns) |
| Hosting | Render free tier + Render cron |
| Frontend | React + Vite |

Everything must run on free tiers. No GPU anywhere.

---

## Hard constraints (from the SRS — do not violate)

- **Recommend, never auto-enroll.** Departments make the final call.
- **No live payments.** Fees and commitments are ledger rows only.
- **No web scraping.** Retrieval runs only over uploaded/mock documents.
- **No training on beneficiary data.**
- **Every match/recommendation shows a plain-language reason**, traceable to a real
  source chunk (`match_record.source_chunk_id`).
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

Since embeddings run locally now (see Stack), only chat/completion calls touch Groq's
rate limit — assistant replies and any generated explanation text. Still worth
precomputing embeddings ahead of the demo for speed, but it's no longer required to dodge
a quota.

---

## Resolved

- **Embeddings provider.** Groq has no embeddings endpoint. Decided: `sentence-transformers`
  running locally (`BAAI/bge-small-en-v1.5`, 384-dim) — Groq stays generation-only.
  Bends the "no models on team hardware" line in the Team Work Division doc; worth a
  one-line heads-up to the team since it's a stated principle, but a 130MB CPU embedding
  model isn't the GPU-inference risk that line was written to prevent.
- **Vector dimension** — `vector(384)`, falls out of the model above. **Tell P3** — this
  is a schema column type they own.

## Open questions blocking architecture lock

Shareable, team-facing version of this whole list (plain + technical language, proposed
defaults, the full API contract proposal): [docs/Pre_Build_Decisions.md](docs/Pre_Build_Decisions.md).

### Needs a whole-team decision

1. **API contract.** Only `POST /profile` is specified anywhere. Every endpoint,
   request/response shape, and error format needs agreement before `services/api`, both
   portals, and my packages can build against a stable target in parallel — this is the
   whole premise the build order depends on.
2. **Trigger execution model — sync or async?** SRS 11.1 implies registration blocks on
   results ("lands on a results screen... right then"). But triggers 5/6/13 re-scan *all*
   beneficiaries when a program changes — that can't reasonably block an admin's HTTP
   request, and no queue/worker infra (Celery, Redis, etc.) is named anywhere for a single
   Render free-tier service. Needs an explicit answer, not an assumption baked into code.
3. **Auth/authorization model.** Architecture's diagram says "demo-scope auth" with
   nothing further — no login flow, no beneficiary-vs-department role distinction, no
   session strategy specified anywhere.
4. **The seven program domains are never listed.** SRS §1 says Al-Khidmat runs "seven
   distinct domain areas" and names four as examples (education, healthcare, financial
   support, vocational training). The other three are undefined — blocks Data
   Engineering's synthetic dataset and Eligibility's "consistent across all seven domains"
   requirement (Team_Work_Division 4.2).
5. **Duplicate-found behavior.** Trigger 2 runs detection on every registration, but no
   doc says what happens when one's found — block registration, flag for department
   review, silently merge? Affects Backend (owns the trigger) and the Main Portal (owns
   the resulting UX).
6. **Reason text: templated or LLM-generated?** If eligibility/match reasons are live
   Groq calls rather than filled from a template, re-scan triggers (5, 6, 13) could burst
   dozens of calls at once — precisely the per-minute rate-limit risk Team_Work_Division
   §8 already names as demo risk #1, just not yet connected to this specific decision.

### Mine to decide — surfacing per the "never silently decide" rule, not deciding alone

7. **How marketplace matching decides between the 3 business models** — one embedding
   space with a classifier, or separate retrieval paths per model.
8. **Notification channel for trigger 7** — in-app only, or email/SMS.
9. **Store listing creation flow.** SRS 5.7 implies a manual form in the Marketplace
   Portal; the trigger table (trigger 3) implies auto-creation the moment a profile has
   trade info. My working assumption: auto-create a draft listing on profile save, let the
   portal edit/publish it — but that's a guess, not yet a decision.
10. **Venture "earning" status.** SRS phrasing ("once the venture starts earning")
    implies a real earnings signal, but nothing in the system observes actual revenue —
    there's no payment processing at all. Working assumption: `venture_status` flips from
    `grace_period` to `earning` purely on the clock, driven by the same trigger-9 sweep,
    not by any external evidence. A simplification worth confirming out loud.

### Watch item — a risk our own decision introduced

11. **Render memory budget.** Loading `sentence-transformers` (~130MB) into the same
    free-tier web service as FastAPI + scikit-learn + XGBoost may be tight on Render's
    free-tier RAM ceiling. Mitigation if it bites: lazy-load the embedder as a singleton,
    or split it into its own light process.

### Minor / can defer

12. **Fee figures and commitment cadence** — placeholders in both docs; need real numbers
    before presenting.
13. `consent_flags` on Beneficiary Profile — schema field exists, semantics (what
    consent, gates what behavior) never defined.
14. `store_listings.registration_fee_paid` boolean vs. Donation Ledger's
    `registration_fee` entry — possible redundant source of truth; the boolean probably
    should be derived from ledger existence rather than stored separately.

---

## Repo layout (decided — single monorepo)

```
apps/main-portal/            Person 4 — React + Vite
apps/marketplace-portal/     Me       — React + Vite
services/api/                Person 3 — FastAPI, shared by both portals
packages/rag/                Me       — shared RAG layer (build first, day one)
packages/marketplace/        Me       — 3 business models, lifecycle, fees
packages/eligibility/        Person 1 — scoring engine
packages/dedup/              Person 3 — RapidFuzz duplicate detection
packages/data/                Data Eng role — schema, synthetic data, features (ships first)
packages/nlp_assistant/       Person 4 — free-text parsing + conversational assistant
workflows/                    Cross-cutting — LlamaIndex Workflow trigger definitions
docs/                          SRS.md, Architecture.md, Team_Work_Division.md
```

My work lives in `packages/rag/`, `packages/marketplace/`, and `apps/marketplace-portal/`.

---

## Reference docs

- `docs/SRS.md` — requirements, scope boundaries, system flow
- `docs/Architecture.md` — architecture, data model, end-to-end flow, deployment
- `docs/Team_Work_Division.md` — roles, trigger ownership, build order
