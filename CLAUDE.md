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
| LLM inference | Groq API (Llama / Qwen open-weight) |
| Embeddings | **UNRESOLVED — see Open Questions** |
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

Every Groq call goes through **one wrapper I own**. That wrapper logs `usage`
(`prompt_tokens`, `completion_tokens`, `total_tokens`), model, and call-site to an
`llm_usage` table. Reasons: Groq's free tier is rate-limited per minute and a demo-day
429 kills the presentation; and we need to know the real cost shape of the system.

Precompute all embeddings before the demo. Only assistant replies generate live.

---

## Open questions blocking architecture lock

1. **Embeddings provider.** Groq's official docs list no `/v1/embeddings` endpoint and no
   embedding models — but the architecture doc assumes one. Must be resolved before the
   RAG layer can be built. Whatever we pick fixes the `vector(N)` dimension in the schema,
   which P3 needs.
2. **Vector dimension** — falls out of (1). Schema-blocking for P3.
3. **How marketplace matching actually decides between the 3 business models** — one
   embedding space with a classifier, or separate retrieval paths per model.
4. **Notification channel for trigger 7** — in-app only, or email/SMS.
5. **Fee figures and commitment cadence** — placeholders in both docs; need real numbers
   before presenting.

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
