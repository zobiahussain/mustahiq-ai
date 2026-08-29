# packages/rag — Shared RAG Layer

**Owner:** Marketplace, Business Matching & Shared RAG Layer role.

pgvector tables, the LlamaIndex retrieval pipeline, a local embedding wrapper, and the
Groq client wrapper for generation. Exposed behind a stable internal function signature —
`packages/eligibility` and `packages/nlp_assistant` both call into this rather than
building their own retrieval. **Does not participate in eligibility scoring** — see
[docs/Eligibility_Flow_Explained.md](../../docs/Eligibility_Flow_Explained.md); this
package only ever answers questions and surfaces passages, never decides who qualifies.

**Two clarified new responsibilities**, per that doc:
- **Criteria rule extraction** — a one-off LLM call when a department admin uploads a
  criteria document, drafting `hard_rules` / `soft_signals` / `required_documents` as
  JSON for admin confirmation. Runs once per document, not per registration.
- **Criteria chunking + embedding** — the same document, separately, into
  `program_criteria` for the assistant to retrieve on demand.

**Embedding dimension — unresolved, needs a decision before building.** The real,
committed schema (`packages/data/schema/al_khidmat_core_schema.sql`,
`al_khidmat_marketplace_schema.sql`) uses `vector(768)` throughout, on the assumption of
Groq/`nomic-embed-text` embeddings. That assumption is false — Groq has no embeddings
endpoint, confirmed directly against their API reference. The already-decided fallback
(`sentence-transformers`, `BAAI/bge-small-en-v1.5`) is 384-dim, which doesn't match the
delivered schema. Cleanest fix: switch to a 768-dim local model (e.g.
`BAAI/bge-base-en-v1.5` or `all-mpnet-base-v2`) so the schema needs no migration — but
that's a call to confirm, not something silently picked here. See CLAUDE.md.

**Depends on:** `packages/data` (schema, vector columns).
**Depended on by:** `packages/eligibility`, `packages/nlp_assistant`, `packages/marketplace`.

Must be stable first — two other roles build against it (see build order in
[docs/Team_Work_Division.md](../../docs/Team_Work_Division.md)).
