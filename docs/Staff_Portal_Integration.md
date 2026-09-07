# Staff Portal Integration

The main staff portal is implemented as `apps/main-portal` and calls the FastAPI staff routes under `/portal`. It is separate from `apps/marketplace-portal`; marketplace code, schemas, and beneficiary-facing flows are unchanged.

The portal follows the Al-Khidmat public brand reference from `https://alkhidmat.org/`: official logo, blue/navy/red palette, and local Inter/Poppins font assets. The UI is operational rather than a landing page: staff enter or update beneficiary profiles, review eligibility suggestions, verify real need, run ranking cycles, approve candidates, finalise allocation records, manage duplicate flags, manage program rules, and ask source-backed program questions. A floating support chatbot is also available on the webpage for general questions about Alkhidmat programs, required documents, verification, and next steps.

## Local Demo

The demo uses an isolated SQLite database with synthetic data. It does not require Supabase credentials and does not call an LLM provider.

```powershell
Copy-Item .env.example .env
.venv\Scripts\python.exe -m pip install -r services/api/requirements-staff.txt
$env:PORTAL_DEMO_MODE='true'
$env:STAFF_GENERATION_ENABLED='false'
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8001
```

In another shell:

```powershell
cd apps/main-portal
..\..\.tools\node.exe ..\..\.tools\package\bin\npm-cli.js install
..\..\.tools\node.exe ..\..\.tools\package\bin\npm-cli.js run dev
```

Open `http://127.0.0.1:5174` and choose **Enter the workspace**.

## Live Supabase Mode

For live mode set `PORTAL_DEMO_MODE=false` and provide `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY` in the repo-root `.env`. Staff authentication uses Supabase Auth. The `staff_users.auth_user_id` column must point at the corresponding Supabase Auth user.

Apply the core schema first, then apply the staff portal migration:

```sql
-- packages/data/schema/al_khidmat_core_schema.sql
-- packages/data/migrations/0002_staff_portal_cycles.sql
```

The migration adds immutable ranking-cycle candidate snapshots. It does not modify the marketplace schema.

For source-backed assistant retrieval in live mode, also install the shared RAG dependencies:

```powershell
.venv\Scripts\python.exe -m pip install -r packages/rag/requirements.txt
```

If no `GROQ_API_KEY` or Ollama provider is configured, the assistant still returns source passages and clearly labels the response as source lookup. Criteria drafting from pasted documents requires a configured generation provider.

The public support chatbot intentionally uses only active program descriptions and saved public program/source passages. It does not read beneficiary records, staff records, applications, rankings, or duplicate flags.

By default the public support chatbot sends that limited program context to the shared Ollama/Qwen endpoint:

```env
SUPPORT_CHAT_USE_LLM=true
OLLAMA_URL=http://100.72.1.8:11434
OLLAMA_MODEL=qwen3:4b
```

If Ollama is offline or the machine is not connected to the required Tailscale network, the chatbot returns a clear source-lookup fallback instead of failing silently. Set `SUPPORT_CHAT_USE_LLM=false` to force retrieval-only mode.

## Workflow Behavior

Profile creation runs duplicate detection and eligibility discovery against active programs. Discovery uses rules plus the saved XGBoost scorer; it does not use an LLM.

Programs flagged `requires_explicit_application` can appear as suppressed discovery matches but cannot be added to proactive outreach. (Islamic Microfinance was the original reason for this flag; it is now handled entirely on the marketplace side and is not an eligibility-side program.)

Verification is required before ranking. Verified outcome records store the assessed income, household size, urgency, and demographic factors used by the transparent prioritization rubric.

Ranking cycles snapshot candidates and scores. `entry_path` and AI confidence are excluded from need scoring. Equal scores use application time and application ID as deterministic tie-breakers.

Program policy edits are blocked while a ranking cycle is open. When confirmed rules, weights, active status, explicit-application requirement, or verification validity changes, active and rolled-over applications for that program are marked expired so staff reassess them under the new policy.

Finalisation only records allocation state in the database. It does not transfer money. If an approved candidate's verification expires before finalisation, staff can remove that approval and finalise the rest.

## Staff API Surface

The staff portal primarily uses:

- `GET /portal/config`
- `GET /portal/support/programs`
- `POST /portal/support/chat`
- `POST /portal/demo-session`
- `POST /portal/session`
- `POST /portal/session/refresh`
- `GET /portal/me`
- `GET /portal/workspace`
- `POST /portal/profiles`
- `PUT /portal/profiles/{profile_id}`
- `POST /portal/profiles/{profile_id}/discover`
- `POST /portal/matches/{match_id}/review`
- `POST /portal/applications`
- `POST /portal/verifications`
- `POST /portal/programs`
- `PUT /portal/programs/{program_id}`
- `POST /portal/programs/{program_id}/cycles`
- `POST /portal/cycles/{cycle_id}/candidates/{candidate_id}`
- `POST /portal/cycles/{cycle_id}/finalise`
- `POST /portal/duplicates/{flag_id}`
- `POST /portal/programs/{program_id}/criteria`
- `POST /portal/criteria/draft`
- `POST /portal/assistant`

The older compatibility endpoint `GET /beneficiaries/{beneficiary_id}/matches` is read-only and returns already stored deterministic matches. Use `POST /portal/profiles/{profile_id}/discover` when staff intentionally want to re-run discovery.

## Verification

Backend workflow tests:

```powershell
.venv\Scripts\python.exe -m unittest services.api.tests.test_staff_workflow -v
```

Frontend interaction tests:

```powershell
cd apps/main-portal
..\..\.tools\node.exe ..\..\.tools\package\bin\npm-cli.js test
```

Production frontend build:

```powershell
cd apps/main-portal
..\..\.tools\node.exe ..\..\.tools\package\bin\npm-cli.js run build
```
