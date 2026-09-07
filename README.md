# Mustahiq AI

[![CI](https://github.com/zobiahussain/mustahiq-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/zobiahussain/mustahiq-ai/actions/workflows/ci.yml)

**AI-powered beneficiary matching & resource allocation for Al-Khidmat Foundation** — built for
the Alibaba × GitHub × X hackathon.

Al-Khidmat runs dozens of assistance programs — education, health, orphan care, WASH, disaster
relief, microfinance — but matching beneficiaries to programs today depends on staff memory and
paperwork. Mustahiq AI gives staff one workspace where AI discovers who may qualify, staff verify
real need, and a transparent rubric prioritizes limited resources. A separate, fee-free
marketplace lets microfinance beneficiaries trade skills and goods directly with each other.

## What we built

Two products, one platform:

**Staff Case-Management Portal** (`apps/main-portal`, staff log in via Supabase Auth)

- Profile entry, eligibility discovery review, and outreach pooling
- Verification records, direct applications, ranked candidate cycles, approvals & finalisation
- Duplicate review (CNIC-first, fuzzy-matched)
- Program rule management with AI-assisted criteria drafting from source documents
- A source-backed staff assistant and a floating public chatbot for program questions

**Beneficiary Marketplace** (`apps/marketplace-portal`, phone + SMS OTP login — no passwords)

- A conversational assistant (text or voice, transcribed via Whisper) turns "what I do" into a
  structured listing — there is no form to fill
- Match results with proximity labels; either side may dismiss a match permanently
- Direct browsing/search of the marketplace, independent of matching
- Three business models, zero fees — beneficiaries trade with each other, not with a platform

## How the AI works

Every layer uses the cheapest tool that is actually correct for the job:

1. **Hard rules eliminate** — deterministic Python evaluates each program's `criteria_structured`
   against the profile (pass / fail / incomplete). No AI in elimination.
2. **XGBoost scores confidence** among rule-passers — a *suggestion* for staff review, never an
   automatic application. Trained on 15k synthetic profiles across the 7 real Al-Khidmat areas of
   work (synthetic only — we say so plainly; in production every staff verification becomes a real
   training label, so the platform generates its own training data as it is used).
   Model artifact: [`artifacts/eligibility-scorer/`](artifacts/eligibility-scorer).
3. **A transparent weighted rubric prioritizes** the verified pool. Deliberately *not* a learned
   model: no training labels exist, decisions must be defensible, and weights must be tunable
   without retraining. Weights live as data on each program row.
4. **LLMs only where they help, never in scoring** — Groq generation drafts criteria from source
   documents and powers the staff assistant; hosted Whisper transcribes voice input; local
   `sentence-transformers` embeddings + pgvector provide RAG over program documents; a
   Qwen3:4b endpoint powers the public support chatbot.

### Fairness by design

- `entry_path` (direct vs. AI-identified) **can never enter ranking** — rejected at the schema,
  engine, and API boundary
- Discovery results are suggestions for staff review, never auto-applications
- Every score ships with a human-readable breakdown and confidence band
- Every ranking run is audited: a `ranking_cycles` row snapshots the exact weights used

### The trigger system

Nine events keep matches and rankings current. Seven fire inline, inside the API request that
causes them (registration-time discovery is milliseconds and deterministic — no queue/worker
infrastructure needed). Two are scheduled as Render cron jobs:

- **Ranking cycles** — weekly check, per-program, no-ops unless the program is actually due
- **Marketplace sweep** — daily expiry of stale matches (7 days) and listings (6 months)

`python -m workflows.triggers` prints the authoritative list of all nine.

## Tech stack

Python 3.11+ · FastAPI + Pydantic v2 · XGBoost · Groq API (generation + Whisper) · local
sentence-transformers (`BAAI/bge-base-en-v1.5`) · Supabase Postgres + pgvector · Supabase Auth
(staff) & phone/OTP (beneficiaries) · React + Vite · Render free tier (1 web service + 2 cron
jobs) · SQLite demo mode. Everything runs on free tiers, no GPU.

## Repository layout

```
apps/
  main-portal/        Staff case-management portal (React + Vite)
  marketplace-portal/ Beneficiary marketplace app (React + Vite)
services/api/         FastAPI backend — staff API (app/main.py),
                      marketplace API (main.py), both together (unified.py)
packages/
  eligibility/        Discovery engine + prioritization rubric
  marketplace/        3 business models, matching, no fees
  rag/                Shared RAG layer + criteria extraction
  dedup/              Duplicate detection (CNIC-first, RapidFuzz)
  data/               Supabase schema, synthetic datasets, feature builders
workflows/            Trigger registry + the two scheduled jobs
artifacts/            Trained XGBoost scorer + metadata
.github/workflows/    CI: lint, frontend builds, offline tests
render.yaml           Deployment blueprint (free tier throughout)
```

Each folder has its own `README.md` with setup detail.

## Quickstart (demo mode — zero external accounts)

```bash
cp .env.example .env        # defaults to PORTAL_DEMO_MODE=true (synthetic SQLite data)

cd services/api
pip install -r requirements-staff.txt
uvicorn app.main:app --port 8001
```

In a second terminal:

```bash
cd apps/main-portal
npm install
npm run dev                 # http://127.0.0.1:5174 → "Enter demo workspace"
```

Demo mode seeds a full synthetic casework workspace (staff, beneficiaries, programs, matches)
into SQLite and never calls Supabase or any LLM.

### Marketplace + live mode

```bash
cd services/api
pip install -r ../../requirements.txt -r ../../packages/rag/requirements.txt
uvicorn main:app            # marketplace API; or `uvicorn unified:app` for
                            # marketplace at / and staff at /staff together
```

For live data, set `PORTAL_DEMO_MODE=false` and fill in the variables from
[`.env.example`](.env.example): `DATABASE_URL` (Supabase Postgres + pgvector),
`SUPABASE_URL` / `SUPABASE_ANON_KEY` (staff auth), and optionally `GROQ_API_KEY`
(generation + Whisper) and `OLLAMA_URL` (support chatbot).

## Testing & CI

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every push:

- **Offline unit tests** — no database, no network, no LLM:
  `PYTHONPATH=packages:services/api python -m pytest -q packages/eligibility/tests packages/dedup/tests services/api/tests/test_rubric.py workflows/tests`
- **Frontend builds** for both portals, plus the staff portal's vitest DOM suite
- **Lint** — ruff (`F`, `E9`: undefined names, unused imports, syntax errors) hard-fails

Also available locally: the staff-portal integration suite
(`services/api/tests/test_staff_workflow.py`, re-seeds ~180 synthetic beneficiaries) and the
network-dependent smoke tests (`workflow_dispatch` from the Actions tab).

## Deployment

[`render.yaml`](render.yaml) deploys the whole platform on free tiers: one Python web service
serving both APIs, plus the two cron jobs. The frontends are static Vite builds — host them
anywhere and point `VITE_API_BASE` / `VITE_STAFF_API_BASE` at the API service.

