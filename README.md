# Mustahiq AI

AI-powered unified beneficiary matching & marketplace platform for Al-Khidmat, built for
the Alibaba × GitHub × X hackathon.

Full requirements, architecture, and role breakdown are in [docs/](docs):

- [docs/SRS.md](docs/SRS.md) — what we're building and why
- [docs/Architecture.md](docs/Architecture.md) — system design, data model, deployment
- [docs/Team_Work_Division.md](docs/Team_Work_Division.md) — who owns what
- [docs/Pre_Build_Decisions.md](docs/Pre_Build_Decisions.md) — open decisions to settle before coding starts

## Repo layout

One monorepo, folders split by ownership so five people can work without stepping on each
other. Each has its own `README.md` naming the owning role and what it depends on.

```
apps/
  main-portal/          Main Platform Portal (React + Vite) — NLP/Assistant/Portal role
  marketplace-portal/   Marketplace Portal (React + Vite) — Marketplace/RAG role

services/
  api/                  FastAPI backend both portals call — Backend & Integration role

packages/                 Python packages imported by services/api
  rag/                   Shared RAG layer (pgvector + LlamaIndex + Groq client) — Marketplace/RAG role
  marketplace/           3 business models, venture lifecycle, fees — Marketplace/RAG role
  eligibility/           Eligibility scoring (rules + XGBoost) — Eligibility Engine role
  dedup/                 Duplicate detection (RapidFuzz) — Backend & Integration role
  data/                  Supabase schema, synthetic datasets, features — Data Engineering role
  nlp_assistant/         Free-text parsing + conversational assistant — NLP/Assistant/Portal role

workflows/               LlamaIndex Workflow trigger definitions (cross-cutting, multiple owners)

docs/                    SRS, Architecture, Team Work Division (source of truth)
```

Build order (see [Team_Work_Division.md §6](docs/Team_Work_Division.md#6-build-order)):
`packages/data` schema → `packages/rag` → `packages/eligibility` + `packages/marketplace`
in parallel → `services/api` → both `apps/` portals → `workflows/` wiring last.

## Stack

Python 3.11+, Groq API (inference), Supabase Postgres + pgvector, LlamaIndex, FastAPI +
Pydantic v2, React + Vite, Render (hosting + cron). Everything on free tiers, no GPU.
