# packages/rag — Shared RAG Layer

**Owner:** Marketplace, Business Matching & Shared RAG Layer role.

pgvector tables, the LlamaIndex retrieval pipeline, and the Groq client wrapper. Exposed
behind a stable internal function signature — `packages/eligibility` and
`packages/nlp_assistant` both call into this rather than building their own retrieval.

**Depends on:** `packages/data` (schema, vector columns).
**Depended on by:** `packages/eligibility`, `packages/nlp_assistant`, `packages/marketplace`.

Must be stable first — two other roles build against it (see build order in
[docs/Team_Work_Division.md](../../docs/Team_Work_Division.md)).
