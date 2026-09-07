# Mustahiq AI

A decision-support layer for Al-Khidmat Foundation's beneficiary aid — built for the
first **Alibaba Cloud AI Hackathon in Pakistan**, hosted by Al-Khidmat Foundation.

Al-Khidmat runs many programmes with limited budgets. The hard part isn't wanting to
help — it's deciding *who, among everyone eligible, needs help most*, and being able to
explain the decision. Mustahiq AI sits on top of that process:

- **Eligibility (staff-operated).** A field officer enters a household's situation in
  conversation. The system checks it against every active programme across Al-Khidmat's
  seven areas of work — health, education, disaster relief, clean water, orphan care,
  BanoQabil, community services — using plain hard rules plus an XGBoost confidence score.
  Suggestions go to a staff worklist, never an automatic enrolment. Staff pool a case,
  verify real need on a home visit, and a bi-weekly cycle ranks everyone waiting on one
  transparent, factor-by-factor rubric. How someone was found can never affect their rank.
- **Marketplace (beneficiary-facing, no fees).** Once a beneficiary has a business loan,
  they open a phone app, describe their business by voice in any language, and are matched
  to nearby suppliers, customers, workers or business partners. Al-Khidmat only introduces.

## Run the eligibility demo (no database, no secrets)

The staff portal runs entirely on an isolated SQLite database seeded with **synthetic
data** — no Supabase, no API keys, no LLM provider.

```powershell
# terminal 1 — API
cd services/api
$env:PORTAL_DEMO_MODE='true'; $env:STAFF_GENERATION_ENABLED='false'; $env:SUPPORT_CHAT_USE_LLM='false'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001      # first start seeds ~180 profiles

# terminal 2 — frontend
cd apps/main-portal
npm install && npm run dev
```

Open **http://127.0.0.1:5174** → *Enter the workspace*, then walk the pipeline: register a
beneficiary → *Discovery review* → *Outreach & verification* → *Ranking & allocation*.

The marketplace app (`apps/marketplace-portal` + `services/api/main.py`) additionally needs
a Postgres + pgvector database via `DATABASE_URL` — see `.env.example`.

## Repo layout

One monorepo, folders split by ownership so five people can work in parallel. Each folder
has its own `README.md` naming the owning role.

```
apps/
  main-portal/          Staff portal (React + Vite)
  marketplace-portal/   Marketplace app (React + Vite, phone + SMS-code login)
services/
  api/                  FastAPI — staff routes under /portal (app/), marketplace API (main.py)
packages/
  eligibility/          Hard-rule engine + XGBoost confidence + prioritisation rubric
  marketplace/          3 matching models, proximity re-weighting, logistics, no fees
  rag/                  Embeddings + retrieval + Groq wrapper + the one-off criteria LLM draft
  dedup/                CNIC-first, then RapidFuzz name/phone comparison
  data/                 SQL schema, synthetic data generator, the 57-feature contract
workflows/              The 9-trigger registry + the 2 scheduled jobs (python -m workflows.run)
```

The 7 event triggers run inline in the API request that causes them; the 2 scheduled jobs
(bi-weekly ranking cycle, daily marketplace sweep) run from `python -m workflows.run` —
on any scheduler, or by hand during the demo.

The team's design docs (SRS, architecture, flows, the marketplace spec) are kept
internally rather than in the repo; this README and each folder's `README.md` are the
public overview.

## How the AI is used

- **Eligibility scoring:** deterministic rules + an XGBoost model trained on 15,000
  synthetic profiles (~54,000 labelled rows, held-out ROC-AUC ≈ 0.76). **No LLM anywhere
  in the scoring path.** The score is a suggestion shown as low / medium / high; it never
  decides funding — the transparent rubric does that, and a human allocates.
- **LLM (Groq), used sparingly:** drafting structured rules from a criteria document once
  at upload (a human confirms), parsing a spoken marketplace listing, writing a match
  reason, and answering staff reference questions — always with a citation.
- **Embeddings:** local `sentence-transformers` on CPU (`BAAI/bge-base-en-v1.5`, 768-dim).

## Stack

Python 3.11+ · FastAPI + Pydantic v2 · Postgres + pgvector (Supabase) · Groq (generation
only, free tier) · local `sentence-transformers` embeddings · React + Vite. Runs on a
laptop — no GPU, no cloud hosting needed for the demo.

## Tests

```powershell
python -m pytest packages/eligibility/tests packages/dedup/tests workflows/tests services/api/tests/test_rubric.py
python -m pytest services/api/tests/test_staff_workflow.py    # slower: re-seeds per test
cd apps/main-portal && npm test
```

Each `packages/*/README.md` names what that module does and depends on.
