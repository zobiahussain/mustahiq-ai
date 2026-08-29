# System Architecture

**AI-Powered Unified Beneficiary Matching & Allocation Platform — Al-Khidmat**

## 1. Architecture Overview

Two coded portals over a deployed FastAPI backend, with a single Supabase Postgres
database holding both relational records and vector embeddings, and all model inference
served by the Groq API. The shared retrieval layer sits behind both the Matching Engine
and the Conversational Assistant rather than in the vertical flow — both call into it.

```
AL-KHIDMAT STAFF   (the only people who log in)
        |
        v
[ MAIN PLATFORM PORTAL ]      React + Vite
  - Profile entry, eligibility results
  - Outreach list, verification, ranked pool
  - Department view

[ MARKETPLACE PORTAL ]        React + Vite
  - Store listing creation
  - Business match review + introductions
        |
        v   (both portals call the same backend)
[ API LAYER ]                 FastAPI on Render
  - Profile CRUD, demo-scope auth
  - Exposes matching + workflow results
        |
        v
[ DISCOVERY ENGINE ]          AI — suggestions only
  - Hard rule check (plain Python) -> eliminates
  - XGBoost confidence score      -> ranks the rest
  - NO LLM, NO retrieval in this path (deterministic)
  - programs needing explicit application (microfinance)
    are scored but SUPPRESSED, never pushed to anyone
  - Marketplace business matching (3 models)
        |
        v
[ POTENTIALLY ELIGIBLE POOL ] not applicants, not contacted
        |
        v
[ VERIFICATION GATE ]         staff outreach
  - real need? assisted elsewhere? still eligible?
  - direct applicants pass through here too
  - can FAIL -> exits the pool
        |
        v
[ UNIFIED CANDIDATE POOL ]    both paths converge
        |
        v
[ PRIORITIZATION RUBRIC ]     bi-weekly, per program
  - transparent weights, NOT a learned model
  - entry_path is never an input
        |
        v
[ HUMAN REVIEW + ALLOCATION ] department decides
        |
        v
[ SHARED RAG LAYER ]          LlamaIndex over pgvector
  - Serves the assistant + match explanations
  - NOT used for eligibility scoring
  - Uploaded/mock documents only — no scraping

[ CRITERIA EXTRACTION ]       LLM, ONE-OFF at doc upload
  - drafts hard_rules + soft_signals as JSON
  - department admin CONFIRMS before it takes effect
        |
        v
[ WORKFLOW LAYER ]            LlamaIndex Workflows
  - 8 event triggers + 1 scheduled sweep
  - ALL output lands in the review worklist,
    never delivered to a beneficiary directly
        |
        v
[ CONVERSATIONAL ASSISTANT ]  Groq + shared RAG
        |
        v
[ DATA LAYER ]                Supabase (Postgres + pgvector)
  - Allocation core: potentially_eligible_pool,
    verifications, applications, ranking_cycles
  - embedding columns alongside the rows they describe

[ EXTERNAL ]                  Groq API — generation + embeddings
```

> **Table count note:** this diagram says "13 tables," §5 below says "Nine tables" then
> lists twelve core tables plus nine marketplace tables, and the actual delivered SQL
> (`al_khidmat_core_schema.sql`) says **11 tables** for the core schema. The SQL files are
> the ground truth — treat every table count in this prose as approximate. See CLAUDE.md.

> **Embeddings note:** this document's stack table and code sample (§3.2) say Groq
> provides embeddings. It doesn't — verified directly against Groq's API reference; no
> `/v1/embeddings` endpoint exists. This conflicts with an already-decided, already-shared
> resolution (local `sentence-transformers`). See CLAUDE.md — this needs reconciling, not
> silently picked one way.

The Matching Engine is the piece almost everything depends on — it runs twice, once for
beneficiary-to-program eligibility and once for beneficiary-to-beneficiary marketplace
matching. Both draw on the same retrieval layer and the same database.

## 2. Technology Stack

| Layer | Choice | Owner |
|---|---|---|
| Core language | Python 3.11+ | All |
| Cross-program discovery | scikit-learn + XGBoost — suggestions only | Person 1 |
| Prioritization rubric | Transparent weighted scoring, weights stored per program | Person 1 |
| LLM inference | Groq API (Llama / Qwen open-weight models) | You |
| Embeddings | Groq embeddings endpoint *(see note above — unconfirmed)* | You |
| Database + vector store | Supabase — Postgres with the pgvector extension | Person 3, You |
| RAG framework | LlamaIndex over pgvector | You |
| Trigger layer | LlamaIndex Workflows — event-driven, typed steps | You, Person 1, Person 3 |
| Duplicate detection | RapidFuzz | Person 3 |
| Backend / API | FastAPI + Pydantic v2 | Person 3 |
| Backend hosting | Render | Person 3 |
| Auth | Supabase Auth — staff accounts only, no beneficiary logins | Person 3 |
| Frontend — Main Platform Portal | React + Vite (staff-operated) | Person 4 |
| Frontend — Marketplace Portal | React + Vite (staff + listing views) *(see note — conflicts with Marketplace_Spec)* | You |
| Scheduled jobs | Render cron job — venture grace-period sweep *(stale — see Team_Work_Division note)* | You |

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

### 2.2 Why Hosted Inference

- No team machine has a GPU, so running models locally would be slow enough to put the
  live demo at risk.
- Groq serves open-weight models over an OpenAI-compatible API on a free tier, so the
  client code is a base-URL change away from any other provider if limits become a
  problem.
- Nothing to install, download, or warm up on presentation day.

## 3. Retrieval Layer Design

The retrieval layer is the platform's most-depended-on component: the eligibility engine
calls it for document-based criteria, the assistant calls it for grounded answers, and
marketplace matching calls it for business descriptions. It is exposed behind a stable
internal signature early so the rest of the team can build against it.

### 3.1 Indexed Content

| Table | Vector content | Filtered by |
|---|---|---|
| program_criteria | Chunked eligibility documents per program | domain, program_id, active |
| store_listings | Business/trade descriptions (marketplace module) | cluster, district, trade_category, role |
| ~~beneficiary_profiles~~ | ~~Free-text situation descriptions~~ | ~~district, income_band~~ |

> The `beneficiary_profiles` row above is struck through: §5's data model and the actual
> schema both say profiles carry **no embedding** — "purely structured." This row is
> stale, carried over from an earlier revision before that decision was made.

### 3.2 Reference Implementation

Enabling vector storage and creating an indexed column:

```sql
create extension if not exists vector;

alter table program_criteria
  add column embedding vector(768);

create index on program_criteria
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
  and availability_status = 'seeking'
order by embedding <=> :query_vec
limit 5;
```

Generating an embedding and a grounded answer through the Groq client — **as documented,
this embeddings call does not work; see the note in §1 and §2.**

```python
from groq import Groq

client = Groq(api_key=os.environ['GROQ_API_KEY'])

vec = client.embeddings.create(
    model='nomic-embed-text-v1_5',
    input=listing_description,
).data[0].embedding

answer = client.chat.completions.create(
    model='llama-3.1-8b-instant',
    messages=[{'role': 'user', 'content': grounded_prompt}],
)
```

## 3A. What Runs When — Ingestion vs Scoring

Four mechanisms appear in this system and are easy to confuse. They run at different
times and do different jobs.

| Mechanism | What it does | When | Decides? |
|---|---|---|---|
| LLM extraction | Drafts criteria rules as JSON from a document | Once, at document upload | No — human confirms |
| Hard rule check | Pass/fail against stated policy thresholds | Every registration | Yes — eliminates |
| XGBoost | Confidence among those who passed the rules | Every registration | No — scores |
| RAG retrieval | Fetches passages to answer a question | On demand | No |

Keeping generation out of the scoring loop is a deliberate architectural decision. An LLM
call per program per registration would be slow, rate-limited, and non-deterministic —
and an eligibility result that varies between runs cannot be audited or defended.

### 3A.1 Criteria Document Lifecycle

```
Document uploaded
      |
      +--> LLM extraction --> draft rules --> ADMIN CONFIRMS
      |                                          |
      |                                          v
      |                              programs.criteria_structured
      |                              (read by the scoring path)
      |
      +--> chunk + embed --> program_criteria
                              (read by the assistant, on demand)
```

One document, two independent purposes: it is the source of the rules, and separately the
source the assistant cites. Only the first affects who qualifies.

## 3B. Model Provider — Hosted or Local

Groq and a local Ollama instance are both OpenAI-compatible, so the provider is a
configuration change rather than a code change:

```python
# hosted (default)
client = OpenAI(base_url='https://api.groq.com/openai/v1', api_key=GROQ_KEY)

# local, on the team's GPU machine
client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
```

Generation is freely swappable. Chat output is not stored, so switching provider affects
nothing already in the database.

Embeddings are **NOT** freely swappable. They are stored in `vector(768)` columns. A model
with different dimensions invalidates every stored vector and breaks the column
definition. If the local option is used, it must be `nomic-embed-text`, which is also 768
dimensions.

A local model implies a local backend. The GPU machine has no public address, so a
cloud-hosted backend cannot reach it without tunnelling. The two coherent setups are
all-cloud (hosted backend + Groq) or all-local (backend on the GPU machine + Ollama).

Build against the swappable client from the start so both remain open, but choose the
primary before demo day and rehearse only that one.

> This section still assumes Groq (or `nomic-embed-text` via Ollama) does the embedding.
> Neither matches the already-committed decision to run a local `sentence-transformers`
> model. See CLAUDE.md for the reconciliation.

## 4. UI Design & Portals

Two separate, coded front ends, since the hackathon requires an actual usable product on
screen.

Both portals are staff-facing and sit behind a single staff login. Beneficiaries do not
have accounts.

### 4.1 Main Platform Portal

Covers profile creation, eligibility results, the match review worklist, and the
department view. The worklist is the working screen of the product — both sides of each
match, the score, the plain-language reason, and approve or dismiss actions.

### 4.2 Marketplace Portal

The marketplace runs on the beneficiary app rather than a staff portal. It covers listing
creation via a conversational assistant, business match results, and direct search for
suppliers, workers, partners, or transport. Staff are not involved in marketplace
operation — they run microfinance and read reports.

> This paragraph directly contradicts the opening line of §4 above ("Both portals are
> staff-facing... beneficiaries do not have accounts") within the same document. It
> matches [Marketplace_Spec.md](Marketplace_Spec.md), which is the more detailed and
> internally consistent source — treat that document as authoritative for this question,
> and treat §4's opening line as the stale one. Flagged in CLAUDE.md.

### 4.3 Design Principles

- Profile entry is progressive, not one long form. Staff enters details while talking
  with the person across a desk, and can skip anything they are uncomfortable answering.
  A half-complete profile that still matches three programs beats a complete form nobody
  finished.
- Nothing on screen should feel like an interrogation — short sections, plain wording, and
  no required fields beyond name and district.
- One shared look and feel across both portals — same palette, logo, and typography — even
  though they're separate codebases.
- Every recommendation or match screen shows the plain-language reason next to the
  result, not just a score — staff has to be able to explain a match out loud to the
  person in front of them.
- Usable at typical phone and tablet widths, since field officers will often work away
  from a desk.

### 4.4 Tech

- React + Vite for both portals — fast dev server, instant hot reload, minimal
  configuration.
- FastAPI backend deployed on Render, shared by both portals.
- A lightweight utility-CSS approach — enough to look coherent, not a full design system.

## 5. Data Model

Full `CREATE TABLE` script, with indexes and reference queries, ships alongside these
documents as `al_khidmat_core_schema.sql` (11 tables) and `al_khidmat_marketplace_schema.sql`
— now committed at `packages/data/schema/`.

- **Department** — id, name, domain. Owns programs; its staff see the matches for those
  programs.
- **Staff User** — id, full_name, email, department_id, role (field_officer |
  department_admin | super_admin), active. The only authenticated actor in the system.
- **Beneficiary Profile** — id, full_name, cnic, phone, household_size, dependents,
  monthly_income, employment_status, district, education_level, has_disability,
  prior_assistance_count, domain_attributes (jsonb), staff_notes, completeness_score,
  created_by_staff_id, consent_given, created_at. **Purely structured — no embedding on
  this table.**
- **Program** — id, department_id, name, domain, criteria_structured,
  has_document_criteria, requires_explicit_application, priority_weights (the
  department's prioritization rubric), budget_per_cycle, capacity_per_cycle,
  cycle_frequency_days, verification_valid_days, active
- **Program Criteria Chunk** — id, program_id, chunk_text, embedding
- **Store Listing** — see [Marketplace_Spec.md](Marketplace_Spec.md) and
  `al_khidmat_marketplace_schema.sql` for the full, current field list.
- **Match Record** — id, beneficiary_id, program_id, score, reason, source_chunk_id,
  status (pending_review | pooled | dismissed | suppressed), reviewed_by_staff_id,
  reviewed_at, staff_notes, created_at. Eligibility only; marketplace matches live in
  their own table in the marketplace module.
- **Potentially Eligible Pool** — id, beneficiary_id, program_id, match_record_id,
  added_at, added_by_staff_id, outreach_status. The waiting room between discovery and
  outreach. Not applicants.
- **Verification** — id, beneficiary_id, program_id, conducted_by_staff_id, outcome
  (verified | no_actual_need | assisted_elsewhere | not_eligible | unreachable |
  declined), need_confirmed, urgency_level, assistance_elsewhere, verified_income,
  verified_household_size, program_specific_data, valid_until. The gate every candidate
  passes through, both paths alike.
- **Application** — id, beneficiary_id, program_id, entry_path (direct | ai_identified),
  verification_id, status, need_score, score_breakdown, rank_in_cycle, cycles_waited. THE
  UNIFIED CANDIDATE POOL, where both paths converge.
- **Ranking Cycle** — id, program_id, run_at, pool_size, budget_available,
  capacity_available, weights_snapshot, approved_count, disbursed_count, status. The
  audit trail for each allocation run.
- **Duplicate Flag** — id, profile_a_id, profile_b_id, similarity_score, matched_on,
  status, reviewed_by_staff_id, reviewed_at
- **Marketplace tables** — store_listings, listing_participants, venture_lineage,
  marketplace_matches, logistics_routes, trade_categories, notifications, donations,
  graduation_events. Specified in full in [Marketplace_Spec.md](Marketplace_Spec.md) and
  its own schema file.

One shared Match Record structure serves both eligibility and marketplace matches, which
lets the matching engine, the API, and the workflow layer stay identical for both use
cases. The `source_chunk_id` field points back to the retrieved chunk a reason was drawn
from, so any explanation is traceable to a real document.

The separation between `match_records`, `potentially_eligible_pool`, and `applications` is
what enforces the core principle structurally rather than by convention: a match cannot
become a candidate without a verification row, and a candidate cannot be ranked without a
valid one. The rule is held by the schema, not by application code remembering to check.

`applications.entry_path` is indexed for audit reporting and appears in no ranking query.
`programs.priority_weights` is a fixed set of permitted keys, and `entry_path` is not among
them — the constraint is enforced at rubric-validation time.

Because `source_id` and `target_id` point at different tables depending on `match_type`,
Postgres cannot enforce a foreign key on them. That is the cost of one shared structure;
enforce it in application code.

## 6. End-to-End Flow

| # | What Happens | Tech | Owner |
|---|---|---|---|
| 1 | Staff enters a beneficiary's profile in conversation | Main Platform Portal → POST /profile | Portal + Backend |
| 2 | Free-text input is parsed into structured fields | Groq JSON-mode completion | NLP role |
| 3 | Profile is written to Supabase | Structured insert, no embedding | Backend, Data |
| 4 | Registration event fires the workflow layer | LlamaIndex Workflow | Workflow owners |
| 5 | Eligibility scoring runs against every active program | Rules + XGBoost; retrieval where criteria are document-based | Eligibility Engine |
| 6 | Duplicate check runs | RapidFuzz on identity fields | Backend role |
| 7 | (Marketplace, separate module) a listing is created and matched | Filtered pgvector query over store_listings | Marketplace |
| 8 | Match results are written back with reasons and source chunks | Supabase update, API response | Backend role |
| 9 | Cross-program matches land for staff review | match_records at pending_review | Backend role |
| 10 | Staff pools a match rather than dismissing it | potentially_eligible_pool insert | Portal + Backend |
| 11 | Assessment cycle: staff contacts and verifies the person | verifications insert; may fail and exit the pool | Portal + Backend |
| 11b | Verified candidates join the unified pool | applications insert, entry_path recorded | Backend role |
| 11c | Bi-weekly cycle scores and ranks the whole pool | Prioritization rubric; ranking_cycles insert | Eligibility Engine |
| 11d | Staff reviews the ranking and allocates within budget | applications status → approved / disbursed / rolled_over | Portal + Backend |
| 12 | Staff asks the assistant a follow-up question | Groq completion, grounded via shared RAG | Assistant role |
| 13 | Department views their matched beneficiaries | Main Platform Portal department view | Backend + Portal |
| 14 | A new beneficiary registers, or a program changes | Re-fires steps 4–9 against the existing pool | Workflow owners |
| 15 | Daily sweep expires stale marketplace matches and listings | Scheduled job | Marketplace |

Steps 9 to 11 are the human-in-the-loop gate on the ELIGIBILITY side: nothing produced
automatically reaches a beneficiary until a staff member has judged it. The marketplace
deliberately has no such gate — it runs on the app without staff involvement. Step 14
handles the "day one, day five" scenario, and step 15 is time-based, which no event can
cover.

Each use case above is traced in full, with the tables touched at every step, in the
accompanying [End-to-End Flows](End_to_End_Flows.md) document.

## 7. Trigger Layer

Triggers are declarative, event-driven workflow steps rather than ad-hoc callbacks, so
each trigger's inputs, outputs, and failure behaviour are explicit and independently
testable. Steps that don't depend on each other — eligibility scoring, duplicate
detection, and marketplace matching after a registration — are dispatched concurrently
rather than sequentially.

The system has eight event-driven triggers and one scheduled one. The full inventory with
owners is in [Team_Work_Division.md](Team_Work_Division.md).

- **Event-triggered (primary):** a registration, profile update, new or edited listing,
  or a new or changed programme immediately re-runs the relevant logic against everything
  already in the system.
- **Scheduled (required, not optional):** the bi-weekly ranking cycle, which is how
  allocation actually happens, and a daily sweep that expires stale marketplace matches
  and listings. Both are time-based, so no event can cover them.

An LLM never decides which step runs next — control flow is fixed, and the model only
generates text within a step. This is why the trigger layer is a workflow engine rather
than an agent graph.

## 8. Governance & Boundaries

- The platform recommends — it never auto-enrolls a beneficiary into a program.
  Departments make the final call.
- The platform never contacts a beneficiary directly. Every match is reviewed by a staff
  member, and contact is made by that person.
- Beneficiaries are shown only approved matches. A pending or dismissed match is never
  surfaced to them.
- The marketplace charges nothing at any point and takes no share of business earnings.
  Al-Khidmat introduces only — terms, pricing, delivery, transport costs and disputes are
  entirely between the two businesses, and this is displayed at listing creation and
  again at introduction.
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
| Staff authentication | Supabase Auth — staff accounts only |

Render's free tier sleeps after inactivity and cold-starts slowly; wake the service before
presenting. Groq's free tier is rate-limited per minute, so all embeddings are precomputed
and only assistant replies are generated live.
