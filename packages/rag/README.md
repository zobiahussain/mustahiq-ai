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

**Embedding dimension — resolved 1 Sep 2026: 768, local, CPU.** `sentence-transformers`,
`BAAI/bge-base-en-v1.5` — matches `vector(768)` in the delivered schema exactly, no
migration needed. Still no Groq dependency for embeddings (Groq has no embeddings
endpoint, confirmed directly against their API reference — stays generation-only).

**Layout:**
```
packages/rag/
  requirements.txt
  embeddings.py       -- embed_text(text) -> list[float], 768-dim, lazy-loaded singleton
  smoke_test.py       -- proves the embedding round trip works
  groq_client.py      -- chat() / chat_json(), the ONE place every Groq call goes
                          through. Model = openai/gpt-oss-120b -- confirmed live
                          against the account's real /models list, not docs (Llama
                          is NOT available on this account, despite what Groq's own
                          docs page said).
  smoke_test_groq.py  -- proves the real listing-enrichment prompt works
```
The pgvector/LlamaIndex retrieval pipeline and the criteria extraction step land here
next.

**Depends on:** `packages/data` (schema, vector columns).
**Depended on by:** `packages/eligibility`, `packages/nlp_assistant`, `packages/marketplace`.

Must be stable first — two other roles build against it (see build order in
[docs/Team_Work_Division.md](../../docs/Team_Work_Division.md)).
