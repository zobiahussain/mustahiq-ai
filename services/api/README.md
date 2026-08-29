# services/api — FastAPI Backend

**Owner:** Similarity Matching, Duplicate Detection, Backend & Integration role.

FastAPI + Pydantic v2 layer serving both apps. Owns the Supabase connection layer, the
Render deployment, and **two separate auth flows**:

- **Staff** (Main Platform Portal): Supabase Auth, email + password. field_officer /
  department_admin / super_admin roles gate who can edit program criteria and which
  departments' matches are visible.
- **Marketplace** (beneficiary app): phone number + SMS one-time code, no password.
  Owns the send-code/verify-code mechanics against `beneficiary_app_accounts` and
  `login_otps` (`packages/data/schema/al_khidmat_marketplace_schema.sql`); the
  Marketplace/RAG role builds the app-side login flow that calls it.

Wires together `packages/eligibility`, `packages/marketplace`, `packages/dedup`,
`packages/nlp_assistant`, and `packages/data`.

**Depends on:** `packages/data` (schema), `packages/eligibility` (scoring output).
**Depended on by:** `apps/main-portal`, `apps/marketplace-portal`.
