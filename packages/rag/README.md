# packages/rag — Shared RAG Layer

**Owner:** Marketplace, Business Matching & Shared RAG Layer role.

pgvector tables, the LlamaIndex retrieval pipeline, a local embedding wrapper
(`sentence-transformers`, `BAAI/bge-small-en-v1.5`, 384-dim), and the Groq client wrapper
for generation. Exposed behind a stable internal function signature —
`packages/eligibility` and `packages/nlp_assistant` both call into this rather than
building their own retrieval.

Embeddings run locally, not through Groq (Groq has no embeddings endpoint) — see
[Architecture.md §2.2](../../docs/Architecture.md#22-why-hosted-inference--for-generation-not-embeddings).

**Depends on:** `packages/data` (schema, vector columns).
**Depended on by:** `packages/eligibility`, `packages/nlp_assistant`, `packages/marketplace`.

Must be stable first — two other roles build against it (see build order in
[docs/Team_Work_Division.md](../../docs/Team_Work_Division.md)).
