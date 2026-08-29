# Team Work Division

**AI-Powered Unified Beneficiary Matching & Allocation Platform — Al-Khidmat**

Five-person team, all with AI/ML backgrounds — there is no dedicated frontend or backend
engineer. Every person owns a piece of the AI system first, and picks up backend or
frontend work only where needed to ship that piece. The platform is presented as two coded
portals over a deployed API, since hackathon judging includes seeing and using the
product, not just the logic behind it.

Two access models, deliberate and different. On the **eligibility side**, the platform is
operated by Al-Khidmat staff on a beneficiary's behalf — staff are the only ones who log
in there, and every match is queued for staff review before it ever reaches a
beneficiary. This removes beneficiary authentication, password recovery, and account
management from that half of the build entirely, because receiving assistance should not
require navigating a system.

The **marketplace** is different: a beneficiary owns their listing, updates their own
availability, and receives their own matches directly, so they authenticate themselves —
phone number + SMS one-time code, no password. Allocating limited resources needs human
judgement; introducing two businesses does not, so it isn't routed through staff at all.

No models run on team hardware. All inference goes through the Groq API, and all data —
relational records and vector embeddings alike — lives in a single Supabase Postgres
database. Marketplace and the shared RAG layer are owned by one person, so every role
needing document grounding calls the same service. The platform does not scrape external
websites; retrieval runs only over uploaded or mock documents prepared for the demo.

## 1. Tech Stack

| Layer | Choice | Owner |
|---|---|---|
| Core language | Python 3.11+ | All |
| Cross-program discovery | scikit-learn + XGBoost — suggestions only | Person 1 |
| Prioritization rubric | Transparent weighted scoring, weights stored per program | Person 1 |
| LLM inference | Groq API (Llama / Qwen open-weight models) | You |
| Embeddings | Groq embeddings endpoint *(unconfirmed — see CLAUDE.md)* | You |
| Database + vector store | Supabase — Postgres with the pgvector extension | Person 3, You |
| RAG framework | LlamaIndex over pgvector | You |
| Trigger layer | LlamaIndex Workflows — event-driven, typed steps | You, Person 1, Person 3 |
| Duplicate detection | RapidFuzz | Person 3 |
| Backend / API | FastAPI + Pydantic v2 | Person 3 |
| Backend hosting | Render | Person 3 |
| Auth — staff portal | Supabase Auth, email + password | Person 3 |
| Auth — marketplace app | Phone number + SMS one-time code, no password | Person 3 (schema/verification), You (app-side flow) |
| Frontend — Main Platform Portal | React + Vite (staff-operated) | Person 4 |
| Frontend — Marketplace App | React + Vite (beneficiary-facing) | You |
| Scheduled jobs | Render cron job — daily marketplace expiry sweep | You |

Everything above is free at hackathon scale: Supabase and Render both have free tiers, and
Groq's free tier needs no credit card. Nothing requires a GPU.

## 2. Working Groups

The five roles split into two working groups, based on how tightly the work depends on
itself.

### 2.1 Group 1 — These Two Together

| Role | Covers | Frontend / Backend |
|---|---|---|
| Marketplace, Business Matching & Shared RAG Layer | Marketplace matching (3 business models), venture lifecycle and fees, dummy data, alerts, plus the shared RAG layer and pgvector collections the rest of the system calls into. | Frontend — builds the Marketplace Portal (React + Vite). |
| AI Recommendation & Eligibility Matching Engine | Eligibility scoring (scikit-learn + XGBoost), recommendation reasoning, recommendation-refresh workflow. | Neither — pure scoring logic, exposed through Group 2's API. |

Grouped together because the Eligibility Engine calls the RAG service constantly for
document-based criteria — the tightest dependency in the system.

> "Venture lifecycle and fees" in this row is stale — see §4.1 note below.

### 2.2 Group 2 — These Three Together

| Role | Covers | Frontend / Backend |
|---|---|---|
| Data Engineering & Feature Support | Supabase schema design, synthetic datasets, feature engineering. | Neither — feeds structured data to everyone else. |
| Similarity Matching, Duplicate Detection, Backend & Integration | Eligibility similarity matching, duplicate detection via RapidFuzz, Supabase integration, Render deployment, end-to-end wiring. | Backend — owns the FastAPI layer the whole platform runs on. |
| NLP, Conversational Assistant & Main Platform Portal | Free-text parsing, the conversational assistant (Groq + shared RAG). | Frontend — builds the Main Platform Portal (React + Vite). |

Grouped together because it's a pipeline: the schema has to exist before the backend can
be built against it, and the API has to exist before the portal has anything to call.

Backend lives entirely in Group 2. Frontend is split across two coded portals: Group 2
builds the Main Platform Portal, Group 1 builds the Marketplace Portal — separate
codebases, kept visually consistent.

## 3. Trigger Ownership

Every trigger in the system, who owns it, and whether it fires on an event or a schedule.
Note that triggers 8 and 9 are both scheduled but run on different clocks: ranking is
per-program and bi-weekly; the marketplace sweep is daily and platform-wide.

| # | Fires when | Type | What runs | Owner |
|---|---|---|---|---|
| 1 | Beneficiary registers | Event | Score against all active programs | Person 1 |
| 2 | Profile created | Event | Duplicate detection (CNIC exact, then RapidFuzz) | Person 3 |
| 3 | Match pooled by staff | Event | Add to potentially eligible pool | Person 3 |
| 4 | Verification recorded | Event | Create or link the application | Person 1 |
| 5 | New programme added | Event | Re-scan all existing beneficiaries | Person 1 |
| 6 | Criteria edited | Event | Re-scan all existing beneficiaries | Person 1 |
| 7 | Listing created or edited | Event | Marketplace matching, notify both parties | You |
| 8 | Ranking cycle due | Scheduled (bi-weekly) | Expire stale verifications, score and rank the pool | Person 1 |
| 9 | Daily | Scheduled | Expire stale marketplace matches and listings | You |

**This trigger table completely replaces the previous one.** Compared to the earlier
revision: trigger 2 (duplicate detection) now runs CNIC-first, not vector similarity —
consistent with profiles carrying no embedding. Triggers 3, 4, 8 are new — they didn't
exist before (pooling, verification→application, and the bi-weekly ranking cycle). What
used to be "premium fee paid → re-rank" and "grace period ends → donation commitment" are
both gone — the marketplace no longer has fees. Trigger 9 kept its number but changed
meaning entirely: it used to be the grace-period/donation sweep; it's now a daily
marketplace-listing-expiry sweep. Still mine either way, but it is a different piece of
code than what CLAUDE.md previously described.

Neither scheduled trigger is optional. Trigger 8 is how allocation actually happens —
without it the candidate pool is never ranked. Trigger 9 keeps the marketplace clean,
since expiry is time-based and no event can cover it. Both run as scheduled jobs.

## 4. Role Detail

### 4.1 Marketplace, Business Matching & Shared RAG Layer

**Responsibilities**

- Own the Beneficiary Marketplace end-to-end — matching logic, dummy data, alerts, and
  notifications. No fees to administer — see "No Fees" below.
- Stand up and own the shared RAG layer: pgvector tables, the LlamaIndex retrieval
  pipeline, and the Groq client wrapper.
- Publish the RAG service behind a stable internal function signature early, since two
  other roles build against it.
- Generate the dummy applicant and store-listing profiles needed to demo marketplace
  matching.
- Build the marketplace trigger as a LlamaIndex Workflow — fires on a new or updated
  listing, scans the pool, notifies both sides directly by SMS and email. No staff step —
  see the Marketplace App access model in Architecture.md §4.2.
- Own the scheduled daily sweep (trigger 9) as a Render cron job — expires unanswered
  matches after 7 days and unconfirmed listings after 6 months.
- Build the Marketplace App (React + Vite), sharing the palette, logo, and typography of
  the Main Platform Portal. Beneficiary-facing, phone + SMS OTP login — a separate access
  model from the staff portal's email + password, not a variant of it.

**Three Marketplace Business Models**

| Model | How it works | Example |
|---|---|---|
| 1. Supply-chain pairing | Match a beneficiary supplying a raw material or input with a beneficiary running the end-product business that needs it. | A leather/fabric supplier matched to a cobbler |
| 2. Joint-venture formation | Match two beneficiaries with complementary skills who could combine into a new business rather than a supplier relationship. | A tailor and a fabric/garment shop owner matched to jointly open a boutique |
| 3. Employment | A business needing a skill is matched with a beneficiary who has it — one loan producing two livelihoods. | A growing boutique and a tailor without steady work |

**No Fees**

- Nothing is charged at any point — no registration fee, no ranking fee, no claim on
  business earnings.
- Once a business is established, the app may offer a gentle, voluntary donation option.
  No schedule, no amount owed, no overdue state.
- Al-Khidmat introduces only. Terms, pricing, delivery and disputes are entirely between
  the two businesses.
- Premium ranking was considered and rejected: charging for visibility in a charity
  marketplace means the poorest are seen least, and routing the fee to donations does not
  fix that.

**Dependencies**

- Depends on Data Engineering's Supabase schema (trade/business fields, vector columns).
- Depends on Backend & Integration for deployment and API conventions.
- Is depended on by the Eligibility Engine (RAG for document-based criteria) and the
  Conversational Assistant (RAG for grounded answers) — the platform's most-depended-on
  piece.

### 4.2 Cross-Program Discovery & Prioritization Engine

**Responsibilities**

- Design the cross-program discovery approach — how a profile is scored against program
  criteria to surface suggestions.
- Build hybrid scoring: rule-based hard cutoffs plus an XGBoost layer for soft-match
  probability. This output is a suggestion for staff, never an application.
- For document-based criteria, call the shared RAG service rather than building a
  separate retrieval path.
- Keep the scoring methodology consistent across all seven program domains.
- Build the "why you were matched" reasoning, turning a raw score into a plain-language
  explanation.
- Own the recommendation-refresh workflow (triggers 5 and 6) and profile-update
  re-scoring (trigger 1).
- Build the prioritization rubric — the transparent weighted scoring that ranks the
  unified candidate pool, with per-factor breakdowns stored so any rank can be explained.
- Own the bi-weekly ranking cycle (trigger 8), including expiring stale verifications
  before scoring.
- Keep `entry_path` out of every ranking computation. Candidates found by AI and
  candidates who applied directly must be scored identically.
- Evaluate recommendation quality (precision, recall, hit-rate) and tune against it.

This role grew substantially from the previous revision: it now also owns the
prioritization rubric and the bi-weekly ranking cycle, which didn't exist before.

**Dependencies**

- Depends on Data Engineering's features and the shared RAG service.
- Is depended on by Backend & Integration and the Conversational Assistant.

### 4.3 Data Engineering & Feature Support

**Responsibilities**

- Design the Supabase schema — tables, relationships, and vector columns — as the single
  definition the API and ML code share. **Delivered** — see `packages/data/schema/`.
- Build synthetic beneficiary and program datasets, since real Al-Khidmat data isn't
  available.
- Handle data cleaning and preprocessing.
- Define and engineer the features that drive matching — income bands, family size,
  location clusters, prior assistance history.
- Run exploratory analysis to validate features before the Eligibility Engine builds on
  them.

**Dependencies**

- No upstream dependency — this work must be ready earliest.
- Is depended on by every other role.

### 4.4 Similarity Matching, Duplicate Detection, Backend & Integration

**Responsibilities**

- Build eligibility-side similarity matching between a profile and program requirements.
- Build duplicate detection using RapidFuzz, and own its trigger (trigger 2) — CNIC exact
  match first, then fuzzy name/phone comparison.
- Own the FastAPI layer serving both portals, with Pydantic v2 request/response models.
- Own the Supabase connection layer and the Render deployment.
- Own staff authentication (Supabase Auth) and role permissions (field officer /
  department admin / super admin).
- Coordinate end-to-end integration across the eligibility engine, data layer,
  marketplace module, and assistant.

**Dependencies**

- Depends on Data Engineering's schema and the Eligibility Engine's scoring output.
- Is depended on by both portal owners.

### 4.5 NLP, Conversational Assistant & Main Platform Portal

**Responsibilities**

- Handle the NLP work that lets the system interpret program descriptions and eligibility
  criteria as text.
- Parse free-text beneficiary input into structured profile fields using Groq's JSON-mode
  output.
- Build and own the conversational assistant, grounded via the shared RAG service. Its
  primary user is staff, not the beneficiary directly.
- Build the Main Platform Portal (React + Vite) — profile entry, eligibility results, the
  match review worklist, and the department view.

**Dependencies**

- Depends on the shared RAG service and the FastAPI layer.
- Is what Al-Khidmat staff interact with directly. Beneficiaries never do.

## 5. Dependency Map

| Role | Depends on | Feeds into |
|---|---|---|
| Marketplace & Shared RAG | Data Engineering (schema), Backend (deployment) | Eligibility Engine, Conversational Assistant |
| Eligibility Engine | Data Engineering (features), Shared RAG | Backend (API), Assistant (explanations) |
| Data Engineering | — | All other roles |
| Backend & Integration | Data Engineering, Eligibility Engine | Both portals |
| NLP, Assistant & Main Portal | Shared RAG, Backend API | Staff, who act on beneficiaries' behalf |

## 6. Build Order

1. Data Engineering publishes the Supabase schema — **done**, `packages/data/schema/`.
2. Shared RAG layer comes up next: pgvector tables created, Groq client wrapped,
   retrieval exposed behind a stable signature.
3. Eligibility Engine and Marketplace matching build in parallel against those two
   foundations.
4. FastAPI layer wraps both and deploys to Render; the two portals build against the
   deployed API.
5. Workflows wire the triggers together last, once the functions they call are stable.

## 7. Cross-Group Check-Ins

- Backend & Integration needs the Eligibility Engine's scoring output before wiring the
  API — one planned sync.
- The Main Platform Portal needs the RAG service and marketplace output before finalizing
  anything shared between portals — a second planned sync.

Two check-ins is a manageable amount of cross-group coordination for a hackathon timeline.

## 8. Demo Risks

- Groq's free tier is rate-limited per minute. Precompute every embedding ahead of the
  demo so only assistant replies are generated live.
- Render's free tier sleeps after inactivity and cold-starts slowly. Wake the service
  before presenting.
- The shared RAG layer blocks two other roles. If it slips, they stall — get it stable on
  day one.
