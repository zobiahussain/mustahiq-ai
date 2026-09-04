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

**`main.py` — the marketplace slice's endpoints, built and tested 4 Sep 2026.** This is
still nominally P3's ownership (the role note above stands), but the marketplace
app-side endpoints exist now, as real running code, tested with actual HTTP requests
against the live Supabase database: `POST /auth/request-otp`, `POST /auth/verify-otp`,
`GET /me/context`, `POST /listing/extract`, `POST /listing`, `GET
/listing/{id}/matches` (this last one added here — not in the originally locked
contract, but nothing shows a beneficiary their matches without it). Every route is a
thin wrapper — the actual logic lives in, and was already independently tested in,
`packages/marketplace/*.py`. Login tokens (JWT) are issued and checked here, not in
`packages/marketplace/auth.py`, which stays framework-agnostic on purpose. The
eligibility-side endpoints (`POST /profile` and everything else in Open Question 1)
are not touched by this file.

**Hosting:** Render free tier, per the stack table — `requirements.txt` in this folder
is what Render installs. Not yet deployed; run locally with
`uvicorn main:app --port 8000` from this folder (needs the repo-root `.env`, and the
`packages/rag` venv's dependencies — `pip install -r requirements.txt` here plus
`../../packages/rag/requirements.txt` covers everything this file imports).
