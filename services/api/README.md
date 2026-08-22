# services/api — FastAPI Backend

**Owner:** Similarity Matching, Duplicate Detection, Backend & Integration role.

FastAPI + Pydantic v2 layer serving both portals. Owns the Supabase connection layer and
the Render deployment. Wires together `packages/eligibility`, `packages/marketplace`,
`packages/dedup`, `packages/nlp_assistant`, and `packages/data`.

**Depends on:** `packages/data` (schema), `packages/eligibility` (scoring output).
**Depended on by:** `apps/main-portal`, `apps/marketplace-portal`.
