# Mustahiq AI

AI-powered unified beneficiary matching and allocation platform for Al-Khidmat, built for the Alibaba x GitHub x X hackathon. Staff-operated case management discovers who may qualify, staff verify real need, and a transparent rubric prioritizes limited resources. A separate, fee-free marketplace connects microfinance beneficiaries to each other.

Full requirements, architecture, and role breakdown are in [docs/](docs):

- [docs/SRS.md](docs/SRS.md) - what we're building and why
- [docs/Architecture.md](docs/Architecture.md) - system design, data model, deployment
- [docs/Team_Work_Division.md](docs/Team_Work_Division.md) - who owns what
- [docs/Eligibility_Flow_Explained.md](docs/Eligibility_Flow_Explained.md) - where the LLM runs vs. XGBoost vs. rules vs. RAG, and why
- [docs/End_to_End_Flows.md](docs/End_to_End_Flows.md) - all use cases traced step by step
- [docs/Marketplace_Spec.md](docs/Marketplace_Spec.md) - full marketplace module spec
- [docs/Staff_Portal_Integration.md](docs/Staff_Portal_Integration.md) - how to run, configure, and verify the implemented staff portal

## Repo Layout

```text
apps/
  main-portal/          Main Platform Portal (React + Vite, staff-facing)
  marketplace-portal/   Marketplace app (React + Vite, beneficiary-facing)

services/
  api/                  FastAPI backend both apps call

packages/
  rag/                  Shared RAG layer + criteria extraction
  marketplace/          3 business models, matching, no fees
  eligibility/          Discovery engine + prioritization rubric
  dedup/                Duplicate detection helpers
  data/                 Supabase schema, migrations, synthetic datasets, features
  nlp_assistant/        Free-text parsing + conversational assistant

docs/                   SRS, architecture, flows, marketplace spec, staff portal runbook
workflows/              Workflow trigger definitions
```

The staff portal can be run locally in demo mode without Supabase credentials. See [docs/Staff_Portal_Integration.md](docs/Staff_Portal_Integration.md).

## Stack

Python 3.11+, FastAPI + Pydantic v2, Supabase Postgres/Auth, pgvector, React + Vite, saved eligibility scorer, optional Groq/Ollama generation, and local `sentence-transformers` embeddings for live RAG retrieval.
