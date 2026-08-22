# System Architecture

**AI-Powered Unified Beneficiary Matching & Marketplace Platform — Al-Khidmat**

## 1. Architecture Overview

Two coded portals over a deployed FastAPI backend, with a single Supabase Postgres
database holding both relational records and vector embeddings, and all model inference
served by the Groq API. The shared retrieval layer sits behind both the Matching Engine
and the Conversational Assistant rather than in the vertical flow — both call into it.

```
BENEFICIARY / DEPARTMENT
        |
        v
[ MAIN PLATFORM PORTAL ]      React + Vite
  - Profile entry, recommendations, department view

[ MARKETPLACE PORTAL ]        React + Vite
  - Store listing creation, match results, alerts
        |
        v   (both portals call the same backend)
[ API LAYER ]                 FastAPI on Render
  - Profile CRUD, demo-scope auth
  - Exposes matching + workflow results
        |
        v
[ AI MATCHING ENGINE ]
  - Eligibility scoring (rules + XGBoost)
  - Marketplace business matching (3 models)
        |
        v
[ SHARED RAG LAYER ]          LlamaIndex over pgvector
  - Chunking, retrieval, citations
  - Uploaded/mock documents only — no scraping
        |
        v
[ WORKFLOW LAYER ]            LlamaIndex Workflows
  - 8 event triggers + 1 scheduled sweep
        |
        v
[ CONVERSATIONAL ASSISTANT ]  Groq + shared RAG
        |
        v
[ DATA LAYER ]                Supabase (Postgres + pgvector)
  - beneficiaries, programs, listings, matches, donation ledger
  - embedding columns alongside the rows they describe

[ EXTERNAL ]                  Groq API — generation + embeddings
```

The Matching Engine is the piece almost everything depends on — it runs twice, once for
beneficiary-to-program eligibility and once for beneficiary-to-beneficiary marketplace
matching. Both draw on the same retrieval layer and the same database.

## 2. Technology Stack

| Layer | Choice | Owner |
|---|---|---|
| Core language | Python 3.11+ | All |
| Eligibility scoring / ML | scikit-learn + XGBoost | Person 1 |
| LLM inference (generation only) | Groq API (Llama / Qwen open-weight models) | You |
| Embeddings | `sentence-transformers`, local CPU — `BAAI/bge-small-en-v1.5` (384-dim) | You |
| Database + vector store | Supabase — Postgres with the pgvector extension | Person 3, You |
| RAG framework | LlamaIndex over pgvector | You |
| Trigger layer | LlamaIndex Workflows — event-driven, typed steps | You, Person 1, Person 3 |
| Duplicate detection | RapidFuzz | Person 3 |
| Backend / API | FastAPI + Pydantic v2 | Person 3 |
| Backend hosting | Render | Person 3 |
| Frontend — Main Platform Portal | React + Vite | Person 4 |
| Frontend — Marketplace Portal | React + Vite (separate portal) | You |
| Scheduled jobs | Render cron job — venture grace-period sweep | You |

> **Decided (Aug 2026):** Groq has no embeddings endpoint. Embeddings run locally via
> `sentence-transformers` instead — see §2.2. Groq is used for generation only: assistant
> replies, JSON-mode field parsing, and match-reason text. This fixes the vector column
> dimension at 384 (see §3.2).

### 2.1 Why One Database Instead of a Separate Vector Store

Embeddings live in pgvector columns in the same Postgres database as the rows they
describe. This matters for correctness, not just convenience: a standalone vector index
cannot apply relational filters, so it would return the top matches by similarity and
leave district, trade category, and active-program filtering to be applied afterwards in
Python — which can return nothing usable after filtering. With pgvector, the filter and
the similarity ranking happen in one query, so ranking only ever applies to genuinely
eligible candidates.

- One system to run, back up, and keep in sync rather than two.
- Filtering, joins, and vector ranking in a single SQL statement.
- Supabase's free tier covers hackathon data volumes.

### 2.2 Why Hosted Inference — For Generation, Not Embeddings

- No team machine has a GPU, so running a generative model locally would be slow enough
  to put the live demo at risk. Groq handles all text **generation**: assistant replies,
  JSON-mode field parsing, and match-reason text.
- Groq serves open-weight models over an OpenAI-compatible API on a free tier, so the
  client code is a base-URL change away from any other provider if limits become a
  problem.
- Nothing to install, download, or warm up on presentation day.
- **Embeddings are different.** Turning text into a vector is a fixed, deterministic
  function — not generation — so there's no quality reason to pay an API round-trip for
  it. `sentence-transformers` (`BAAI/bge-small-en-v1.5`, 384-dim, ~130MB) runs on CPU in
  milliseconds and needs no API key or rate-limit budget. This lightly bends the "no
  models on team hardware" principle, but a 130MB embedding model is not the GPU-class
  inference risk that principle exists to avoid.

## 3. Retrieval Layer Design

The retrieval layer is the platform's most-depended-on component: the eligibility engine
calls it for document-based criteria, the assistant calls it for grounded answers, and
marketplace matching calls it for business descriptions. It is exposed behind a stable
internal signature early so the rest of the team can build against it.

### 3.1 Indexed Content

| Table | Vector content | Filtered by |
|---|---|---|
| program_criteria | Chunked eligibility documents per program | domain, program_id, active |
| store_listings | Business/trade descriptions from listings | district, trade_category, venture_status |
| beneficiary_profiles | Free-text situation descriptions | district, income_band |

### 3.2 Reference Implementation

Enabling vector storage and creating an indexed column:

```sql
create extension if not exists vector;

alter table store_listings
  add column embedding vector(384);

create index on store_listings
  using hnsw (embedding vector_cosine_ops);
```

Filtered similarity search — the pattern used for both eligibility and marketplace
matching. The `WHERE` clause runs alongside the ranking, so only eligible candidates are
ever scored:

```sql
select id, trade, price_range,
       1 - (embedding <=> :query_vec) as score
from store_listings
where district = :district
  and venture_status = 'active'
order by embedding <=> :query_vec
limit 5;
```

Generating an embedding locally, and a grounded answer through the Groq client — two
separate clients because they're two separate jobs:

```python
from sentence_transformers import SentenceTransformer
from groq import Groq

embedder = SentenceTransformer('BAAI/bge-small-en-v1.5')  # loaded once, reused
groq_client = Groq(api_key=os.environ['GROQ_API_KEY'])

vec = embedder.encode(listing_description).tolist()  # 384-dim, runs on CPU, no API call

answer = groq_client.chat.completions.create(
    model='llama-3.1-8b-instant',
    messages=[{'role': 'user', 'content': grounded_prompt}],
)
```

## 4. UI Design & Portals

Two separate, coded front ends, since the hackathon requires an actual usable product on
screen.

### 4.1 Main Platform Portal

For beneficiaries and departments. Covers profile creation, the recommendations view
(matched programs with plain-language reasons), and the department view (matched
beneficiaries per program).

### 4.2 Marketplace Portal

A separate portal for the business-matching side. Covers store listing creation, ranked
match results with reasons and premium listings marked, and alerts when a new match is
found.

### 4.3 Design Principles

- Plain language throughout — many beneficiaries won't be comfortable with a typical web
  app, so screens avoid jargon and keep each step short.
- One shared look and feel across both portals — same palette, logo, and typography — even
  though they're separate codebases.
- Every recommendation or match screen shows the plain-language reason next to the result,
  not just a score.
- Usable at typical phone widths, since beneficiaries would realistically access this from
  a phone.

### 4.4 Tech

- React + Vite for both portals — fast dev server, instant hot reload, minimal
  configuration.
- FastAPI backend deployed on Render, shared by both portals.
- A lightweight utility-CSS approach — enough to look coherent, not a full design system.

## 5. Data Model

- **Beneficiary Profile** — id, personal_info, family_info, income, location,
  trade_or_business (optional), consent_flags, embedding, created_at
- **Program** — id, domain, eligibility_criteria (structured fields OR reference to a
  source document), active
- **Program Criteria Chunk** — id, program_id, chunk_text, embedding
- **Store Listing** — id, beneficiary_id, trade/product, capacity, price_range, location,
  embedding, registration_fee_paid, venture_status (grace_period | earning),
  earning_start_date
- **Match Record** — id, match_type (eligibility | marketplace), match_model
  (supply_chain | joint_venture | competitive_ranking), source_id, target_id, score,
  reason, source_chunk_id, created_at
- **Donation Ledger** — id, store_listing_id, entry_type (registration_fee |
  commitment_payment | premium_fee), amount, date, status

One shared Match Record structure serves both eligibility and marketplace matches, which
lets the matching engine, the API, and the workflow layer stay identical for both use
cases. The `source_chunk_id` field points back to the retrieved chunk a reason was drawn
from, so any explanation shown to a beneficiary is traceable to a real document. The
Donation Ledger is data-only — it records what's owed and paid without processing live
payments.

## 6. End-to-End Flow

| # | What Happens | Tech | Owner |
|---|---|---|---|
| 1 | Beneficiary submits their profile | Main Platform Portal → POST /profile | Portal + Backend |
| 2 | Free-text input is parsed into structured fields | Groq JSON-mode completion | NLP role |
| 3 | Profile and its embedding are written in one transaction | Supabase insert with vector column | Backend, Data |
| 4 | Registration event fires the workflow layer | LlamaIndex Workflow | Workflow owners |
| 5 | Eligibility scoring runs against every active program | Rules + XGBoost; retrieval where criteria are document-based | Eligibility Engine |
| 6 | Duplicate check runs | RapidFuzz on identity fields + vector similarity | Backend role |
| 7 | If trade info exists, a listing is created and matched | Filtered pgvector query over store_listings | Marketplace |
| 8 | Match results are written back with reasons and source chunks | Supabase update, API response | Backend role |
| 9 | Both sides are notified of any marketplace match | Workflow notification step | Marketplace |
| 10 | Results are shown to the beneficiary | Main Platform Portal; Marketplace Portal for business matches | Both portal owners |
| 11 | Beneficiary asks a follow-up question | Groq completion, grounded via shared RAG | Assistant role |
| 12 | Department views their matched beneficiaries | Main Platform Portal department view | Backend + Portal |
| 13 | A new beneficiary registers, or a program changes | Re-fires steps 4–9 against the existing pool | Workflow owners |
| 14 | A venture's grace period ends | Scheduled Render cron job → donation commitment | Marketplace |

Step 13 handles the "day one, day five" scenario — a new event re-checks against
everything already in the system, so a match isn't missed because the two sides showed up
on different days. Step 14 is the one action no event can trigger, since nothing happens
in the system when a grace period simply elapses.

## 7. Trigger Layer

Triggers are declarative, event-driven workflow steps rather than ad-hoc callbacks, so
each trigger's inputs, outputs, and failure behaviour are explicit and independently
testable. Steps that don't depend on each other — eligibility scoring, duplicate
detection, and marketplace matching after a registration — are dispatched concurrently
rather than sequentially.

The system has eight event-driven triggers and one scheduled one. The full inventory with
owners is in [Team_Work_Division.md](Team_Work_Division.md).

- **Event-triggered (primary):** a registration, profile update, new or edited listing,
  new or changed program, a match being found, or a premium fee being paid all immediately
  re-run the relevant logic against everything already in the system.
- **Scheduled (required, not optional):** a daily sweep detects ventures whose grace
  period has ended and starts their donation commitment. Nothing happens in the system
  when a grace period elapses, so no event can cover this case.

An LLM never decides which step runs next — control flow is fixed, and the model only
generates text within a step. This is why the trigger layer is a workflow engine rather
than an agent graph.

## 8. Governance & Boundaries

- The platform recommends — it never auto-enrolls a beneficiary into a program.
  Departments make the final call.
- The platform is a discovery/matching layer for the marketplace — it does not process or
  hold live payments; registration fees, donation commitments, and premium fees are
  recorded in the Donation Ledger as data.
- Beneficiary data is never used to train any model.
- The platform does not scrape external websites — all retrieval runs over uploaded or
  mock documents prepared for the demo.
- Backend and both portals are real, coded implementations built to demo scope;
  production-grade auth, scaling, and payment infrastructure are out of scope and
  whiteboarded.
- This is not a replacement for Al-Khidmat's existing systems and not an attempt at a full
  MIS — it's an intelligence layer sitting on top of what already exists.

## 9. Deployment

| Component | Where it runs |
|---|---|
| FastAPI backend | Render web service (free tier) |
| Scheduled sweep | Render cron job |
| Database + vectors | Supabase managed Postgres (free tier) |
| Model inference | Groq API (free tier) |
| Both portals | Static build — Render static site or equivalent |

Render's free tier sleeps after inactivity and cold-starts slowly; wake the service before
presenting. Groq's free tier is rate-limited per minute, so all embeddings are precomputed
and only assistant replies are generated live.
