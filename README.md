# Mustahiq AI

AI-powered unified beneficiary matching & allocation platform for Al-Khidmat, built for
the Alibaba × GitHub × X hackathon. Staff-operated case management: AI discovers who may
qualify, staff verify real need, a transparent rubric prioritizes limited resources. A
separate, fee-free marketplace connects microfinance beneficiaries to each other.

Full requirements, architecture, and role breakdown are in [docs/](docs):

- [docs/SRS.md](docs/SRS.md) — what we're building and why
- [docs/Architecture.md](docs/Architecture.md) — system design, data model, deployment
- [docs/Team_Work_Division.md](docs/Team_Work_Division.md) — who owns what
- [docs/Eligibility_Flow_Explained.md](docs/Eligibility_Flow_Explained.md) — where the
  LLM runs vs. XGBoost vs. rules vs. RAG, and why
- [docs/End_to_End_Flows.md](docs/End_to_End_Flows.md) — all 11 use cases traced step by
  step
- [docs/Marketplace_Spec.md](docs/Marketplace_Spec.md) — full marketplace module spec

See the root [CLAUDE.md](CLAUDE.md) for open questions and doc-set contradictions still
needing a team decision before these are fully locked.

## Repo layout

One monorepo, folders split by ownership so five people can work without stepping on each
other. Each has its own `README.md` naming the owning role and what it depends on.

```
apps/
  main-portal/          Main Platform Portal (React + Vite, staff-facing) — NLP/Assistant/Portal role
  marketplace-portal/   Marketplace app (React + Vite, beneficiary-facing) — Marketplace/RAG role

services/
  api/                  FastAPI backend both apps call, staff auth — Backend & Integration role

packages/                 Python packages imported by services/api
  rag/                   Shared RAG layer + criteria extraction — Marketplace/RAG role
  marketplace/           3 business models, matching, no fees — Marketplace/RAG role
  eligibility/           Discovery engine + prioritization rubric — Eligibility Engine role
  dedup/                 Duplicate detection (CNIC-first, RapidFuzz) — Backend & Integration role
  data/                  Supabase schema (delivered, schema/), synthetic datasets, features — Data Engineering role
  nlp_assistant/         Free-text parsing + conversational assistant — NLP/Assistant/Portal role

workflows/               LlamaIndex Workflow trigger definitions (cross-cutting, multiple owners)

docs/                    SRS, Architecture, Team Work Division, Eligibility Flow, End-to-End Flows, Marketplace Spec
```

Build order (see [Team_Work_Division.md §6](docs/Team_Work_Division.md#6-build-order)):
`packages/data` schema (delivered) → `packages/rag` → `packages/eligibility` +
`packages/marketplace` in parallel → `services/api` → both `apps/` → `workflows/` wiring
last.

## Stack

Python 3.11+, Groq API (generation only), local `sentence-transformers` embeddings,
Supabase Postgres + pgvector, LlamaIndex, FastAPI + Pydantic v2, Supabase Auth
(staff-only), React + Vite, Render (hosting + cron). Everything on free tiers, no GPU.
