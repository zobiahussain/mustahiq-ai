# packages/eligibility — Eligibility Scoring Engine

**Owner:** AI Recommendation & Eligibility Matching Engine role.

Hybrid scoring: rule-based hard cutoffs + XGBoost soft-match probability. "Why you were
matched" reasoning. Owns triggers 3 (eligibility half), 5, 6.

**Depends on:** `packages/data` (features), `packages/rag` (document-based criteria).
**Depended on by:** `services/api`, `packages/nlp_assistant` (explanations).
