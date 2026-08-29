# packages/eligibility — Cross-Program Discovery & Prioritization Engine

**Owner:** AI Recommendation & Eligibility Matching Engine role.

**Scope grew substantially** from the earlier revision — this package now owns two
distinct stages, not one:

1. **Discovery** (every registration): hard-rule pass/fail (plain Python, reads
   `programs.criteria_structured`) eliminates; XGBoost then scores confidence among
   survivors. A suggestion for staff, never an application. No LLM, no retrieval in this
   path — see [docs/Eligibility_Flow_Explained.md](../../docs/Eligibility_Flow_Explained.md)
   for why generation is deliberately kept out of scoring.
2. **Prioritization** (bi-weekly per program, new): the transparent weighted rubric that
   ranks the *unified candidate pool* (verified candidates only) — not a learned model,
   for reasons laid out in that same doc (no training labels, needs to be defensible,
   needs to be tunable without retraining). Weights live as data on the program row.
   `entry_path` (direct vs. ai_identified) must never enter this computation.

**Triggers owned:** 1 (registration → score against all programs), 4 (verification
recorded → create/link application), 5 (new program → re-scan all beneficiaries), 6
(criteria edited → re-scan all beneficiaries), 8 (bi-weekly ranking cycle — expire stale
verifications, then score and rank).

**XGBoost training data:** synthetic only for the hackathon (Al-Khidmat has no historical
decisions to learn from) — say so plainly, don't imply otherwise. In production, every
`verifications` row becomes a real training label (did outreach confirm what discovery
predicted?), so the platform generates its own training data as it's used.

**Depends on:** `packages/data` (features), `packages/rag` (document-based criteria, on
demand only — never in the scoring path).
**Depended on by:** `services/api`, `packages/nlp_assistant` (explanations).
