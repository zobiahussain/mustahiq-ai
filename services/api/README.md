# services/api — FastAPI Backend

**Owner:** Similarity Matching, Duplicate Detection, Backend & Integration role.

FastAPI + Pydantic v2 layer serving both portals. Owns the Supabase connection layer, the
Render deployment, and **staff authentication** (Supabase Auth — staff accounts only;
field_officer / department_admin / super_admin roles gate who can edit program criteria
and which departments' matches are visible). Wires together `packages/eligibility`,
`packages/marketplace`, `packages/dedup`, `packages/nlp_assistant`, and `packages/data`.

There is no beneficiary auth on the eligibility side — beneficiaries never log in. The
marketplace app's access model is a separate, still-open question; see
`apps/marketplace-portal/README.md`.

**Depends on:** `packages/data` (schema), `packages/eligibility` (scoring output).
**Depended on by:** `apps/main-portal`, `apps/marketplace-portal`.
