# Team Work Division

**AI-Powered Unified Beneficiary Matching & Marketplace Platform — Al-Khidmat**

Five-person team, all with AI/ML backgrounds — there is no dedicated frontend or backend
engineer. Every person owns a piece of the AI system first, and picks up backend or
frontend work only where needed to ship that piece. The platform is presented as two coded
portals over a deployed API, since hackathon judging includes seeing and using the
product, not just the logic behind it.

No models run on team hardware. All inference goes through the Groq API, and all data —
relational records and vector embeddings alike — lives in a single Supabase Postgres
database. Marketplace and the shared RAG layer are owned by one person, so every role
needing document grounding calls the same service. The platform does not scrape external
websites; retrieval runs only over uploaded or mock documents prepared for the demo.

## 1. Tech Stack

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
Triggers 3, 7, 8 and 9 were implicit in the original specification and are now assigned
explicitly.

| # | Fires when | Type | What runs | Owner |
|---|---|---|---|---|
| 1 | Beneficiary registers | Event | Score against all active programs | Person 1 |
| 2 | Beneficiary registers | Event | Duplicate detection against existing records | Person 3 |
| 3 | Profile updated | Event | Re-score eligibility; create listing if trade info added | Person 1, You |
| 4 | Store listing created or edited | Event | Match against the existing listing pool | You |
| 5 | New program added | Event | Re-scan all existing beneficiaries | Person 1 |
| 6 | Eligibility criteria edited | Event | Re-scan all existing beneficiaries | Person 1 |
| 7 | Match found | Event | Notify both sides | You |
| 8 | Premium fee paid | Event | Re-rank that listing in existing match results | You |
| 9 | Grace period ends | Scheduled | Start the donation commitment schedule | You |

Trigger 9 is the only scheduled one — nothing happens in the system when a grace period
ends, so no event can fire. It runs as a Render cron job and is required for the venture
lifecycle demo, not optional.

## 4. Role Detail

### 4.1 Marketplace, Business Matching & Shared RAG Layer

**Responsibilities**

- Own the Beneficiary Marketplace end-to-end — matching logic, lifecycle and fee rules,
  dummy data, alerts, and notifications.
- Stand up and own the shared RAG layer: pgvector tables, the LlamaIndex retrieval
  pipeline, and the Groq client wrapper.
- Publish the RAG service behind a stable internal function signature early, since two
  other roles build against it.
- Generate the dummy applicant and store-listing profiles needed to demo marketplace
  matching.
- Build the marketplace trigger as a LlamaIndex Workflow — fires on a new or updated
  listing, scans the pool, surfaces matches as alerts, notifies both sides.
- Own the scheduled grace-period sweep (trigger 9) as a Render cron job.
- Build the Marketplace Portal (React + Vite), sharing the palette, logo, and typography
  of the Main Platform Portal.

**Three Marketplace Business Models**

| Model | How it works | Example |
|---|---|---|
| 1. Supply-chain pairing | Match a beneficiary supplying a raw material or input with a beneficiary running the end-product business that needs it. | A leather/fabric supplier matched to a cobbler |
| 2. Joint-venture formation | Match two beneficiaries with complementary skills who could combine into a new business rather than a supplier relationship. | A tailor and a fabric/garment shop owner matched to jointly open a boutique |
| 3. Competitive ranking | A beneficiary offering goods or services similar to others can pay a premium fee to rank above unboosted competitors in match results. | Two shoe sellers on the marketplace; one pays to rank first |

**Venture Lifecycle & Fee Structure**

- A flat, one-time registration fee is charged when a store listing is first created.
- A grace period of roughly six months to a year follows, during which no earnings-based
  commitment applies.
- Once the venture starts earning, a recurring donation commitment begins — periodic
  payments over the following year — flowing back into Al-Khidmat's donation pool.
- Premium ranking fees route into the same donation pool rather than being kept as
  platform revenue.
- Exact fee amounts and the donation-commitment cadence are placeholders — confirm the
  figures before presenting.

**Dependencies**

- Depends on Data Engineering's Supabase schema (trade/business fields, vector columns).
- Depends on Backend & Integration for deployment and API conventions.
- Is depended on by the Eligibility Engine (RAG for document-based criteria) and the
  Conversational Assistant (RAG for grounded answers) — the platform's most-depended-on
  piece.

### 4.2 AI Recommendation & Eligibility Matching Engine

**Responsibilities**

- Design the eligibility scoring approach — how a profile is scored against program
  criteria.
- Build hybrid scoring: rule-based hard cutoffs plus an XGBoost layer for soft-match
  probability.
- For document-based criteria, call the shared RAG service rather than building a
  separate retrieval path.
- Keep the scoring methodology consistent across all seven program domains.
- Build the "why you were matched" reasoning, turning a raw score into a plain-language
  explanation.
- Own the recommendation-refresh workflow (triggers 5 and 6) and profile-update
  re-scoring (trigger 3).
- Evaluate recommendation quality (precision, recall, hit-rate) and tune against it.

**Dependencies**

- Depends on Data Engineering's features and the shared RAG service.
- Is depended on by Backend & Integration and the Conversational Assistant.

### 4.3 Data Engineering & Feature Support

**Responsibilities**

- Design the Supabase schema — tables, relationships, and vector columns — as the single
  definition the API and ML code share.
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
- Build duplicate detection using RapidFuzz, and own its trigger (trigger 2).
- Own the FastAPI layer serving both portals, with Pydantic v2 request/response models.
- Own the Supabase connection layer and the Render deployment.
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
- Build and own the conversational assistant, grounded via the shared RAG service.
- Build the Main Platform Portal (React + Vite) — profile entry, recommendations view,
  department view.

**Dependencies**

- Depends on the shared RAG service and the FastAPI layer.
- Is what beneficiaries and departments interact with directly.

## 5. Dependency Map

| Role | Depends on | Feeds into |
|---|---|---|
| Marketplace & Shared RAG | Data Engineering (schema), Backend (deployment) | Eligibility Engine, Conversational Assistant |
| Eligibility Engine | Data Engineering (features), Shared RAG | Backend (API), Assistant (explanations) |
| Data Engineering | — | All other roles |
| Backend & Integration | Data Engineering, Eligibility Engine | Both portals |
| NLP, Assistant & Main Portal | Shared RAG, Backend API | Beneficiaries / departments |

## 6. Build Order

1. Data Engineering publishes the Supabase schema — everything else builds on it.
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
