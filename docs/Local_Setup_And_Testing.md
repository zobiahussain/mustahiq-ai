# Local Setup and Testing — for a new machine

Everything needed to get this repo running on a different computer and start testing the
marketplace module for real: what to download, what to set up, and how to create test
customers and exercise the eligibility gate and the webhook triggers. Written for the
Marketplace/RAG slice (`packages/rag`, `packages/marketplace`, `services/api`'s
marketplace routes, `apps/marketplace-portal`) — not the whole platform.

---

## 1. Clone the repo

```
git clone https://github.com/zobiahussain/mustahiq-ai
cd mustahiq-ai
git checkout zobia
```

Everything you need lives inside this one repo — there's no second download.

---

## 2. Two files to bring over yourself — everything else is on GitHub

Confirmed directly (`git status --ignored`), not assumed: only two files in this repo
need manual copying. Everything else either pushes with the repo or regenerates itself in
section 3/4 below (`node_modules/`, `packages/rag/.venv/`, `__pycache__/`, and
`packages/data/exports/` are all gitignored but don't need copying — they're rebuilt by
`npm install`/`pip install`, or by rerunning a script).

**`.env`** — gitignored on purpose. A database password and API keys should never sit in
git history, even a private repo. Copy it (USB, a private note to yourself, whatever
channel you're comfortable with — never paste it into a GitHub issue, Slack, or anywhere
public) and drop it at the **repo root** on the new machine, next to `CLAUDE.md`. It
currently holds:

```
SUPABASE_PROJECT_URL=...
anon_public_key=...
service_role_key=...
GROQ_API_KEY=...
DATABASE_URL=...
JWT_SECRET=...
SKIP_ELIGIBILITY_CHECK=true      # see section 5 below — you may want this false
INTERNAL_API_KEY=...             # gates the webhook endpoints, see section 6
```

Every Python file that needs the database or Groq loads this same file — nothing needs a
second copy anywhere else in the repo.

**`marketplace_listing_build_flowchart.png`** (repo root, ~955 KB) — the only OTHER file
that needs manual copying. Not gitignored, just genuinely never committed (sitting there
since 1 Sep 2026) — a real gap, confirmed by checking `git status` directly rather than
assuming everything at the repo root is tracked. Left untracked deliberately (not pushed)
— copy it the same way as `.env` if you want it on the new machine, or skip it if you
don't need it there.

---

## 3. Python setup — one shared virtual environment

There's no separate venv per package. `packages/marketplace` and `services/api` both
import straight from `packages/rag` rather than being installed as separate packages, so
one venv at `packages/rag/.venv` covers everything Python-related in this repo.

```powershell
cd packages\rag
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r ..\..\services\api\requirements.txt
```

Needs Python 3.11+ already on the machine (`python --version` to check).

---

## 4. Node setup — the marketplace app

```powershell
cd apps\marketplace-portal
npm install
```

No `.env` needed here for local dev — `src/api.js` defaults to `http://localhost:8000`
when nothing's set.

---

## 5. VS Code

- Open the repo root as the workspace folder.
- Install the **Python** extension if it isn't already there.
- `Ctrl+Shift+P` → "Python: Select Interpreter" → `packages\rag\.venv\Scripts\python.exe`.
  Without this, imports show red squiggles because VS Code defaults to a global Python
  that doesn't have `fastapi`/`sentence-transformers`/`groq` installed.

---

## 6. Running it

```powershell
# terminal 1 — backend
cd services\api
..\..\packages\rag\.venv\Scripts\uvicorn main:app --port 8000

# terminal 2 — frontend
cd apps\marketplace-portal
npm run dev
```

First request that touches embeddings pauses a few seconds to load the model from the
local Hugging Face cache (no network call needed if it's already cached — see
`packages/rag/embeddings.py`'s docstring on `HF_HUB_OFFLINE`). The API server also warms
this at startup now, so it's usually already done by the time you make your first
request.

Sanity check everything's wired up correctly, without opening the frontend at all:

```powershell
cd packages\marketplace
..\rag\.venv\Scripts\python.exe smoke_test_graduation.py
```

`ALL GRADUATION CHECKS PASS.` at the end means the DB connection, Groq key, and embedding
model are all confirmed working.

---

## 7. The eligibility gate — keep it real, toggle it only when you need to

**Recommendation: leave `SKIP_ELIGIBILITY_CHECK=false` (or delete the line entirely) as
the normal state.** The actual product rule (Marketplace_Spec.md §2) is that only a phone
number with a `microfinance_loans` row — `status` `approved` or `disbursed`, with a real
`trade_category_id` set — can create a marketplace account. Anyone else can still log in
(the gate isn't about denying the app, just listing creation), but a number with **no**
matching `beneficiary_profiles` row at all is rejected before an OTP is even sent. That's
the real behavior, and it's worth testing against directly, not just trusting the code.

`SKIP_ELIGIBILITY_CHECK=true` exists purely as a **speed toggle** for iterating on
frontend/UI work quickly, where you don't care who's logging in — any phone number works,
auto-provisioned with a generic profile. Flip it on for that kind of session, flip it back
to `false` (or remove it) once you're testing anything gate-related, and always before
anything resembling a demo — `auth.py` prints a loud warning on every use specifically so
this can't be silently forgotten.

Restart the API server after changing it — `.env` is only read at process startup.

---

## 8. Creating test customers, for real, with validation ON

This is the part that actually needed building — until now there was no way to insert a
"real" customer (the kind the eligibility gate checks for) without either the
`SKIP_ELIGIBILITY_CHECK` bypass or hand-writing SQL. There is still no `POST /profile`
endpoint anywhere in this repo (that's the eligibility side's job, not built yet) — these
two scripts are the stand-in, mirroring exactly what a loan officer would enter at a
facilitation centre.

### 8a. One customer at a time

```powershell
cd packages\data
..\rag\.venv\Scripts\python.exe create_test_customer.py --phone "+923005559999" --name "Rukhsana Bibi" --district "Multan" --category "Tailoring & embroidery" --status approved
```

Or run it with no arguments and it prompts you for each field one at a time.

`--status` defaults to `approved` (eligible from approval, per §2 — doesn't need to wait
for disbursement). Use `--status disbursed` / `defaulted` / `rejected` to test the other
gate outcomes, or `--category ""` (empty) to simulate a Liberation-Loan-style loan with no
business — can log in, never offered listing creation.

The script prints the exact next commands to run — copy-paste them straight from the
terminal.

### 8b. Many at once — the spreadsheet way

Open `packages/data/test_customers_template.csv` in Excel. It already has the header row
set up:

```
phone,full_name,district,trade_category,status
```

Delete the two example rows (or keep them, they're harmless test data), add one row per
customer you want, save as CSV, then run:

```powershell
cd packages\data
..\rag\.venv\Scripts\python.exe import_test_customers.py
```

(Or point it at a different file: `import_test_customers.py my_customers.csv`.)

- `trade_category` — one of the 10 real names (`packages/data/reference_lists.md`), or
  leave the cell blank for "not a business."
- `status` — blank defaults to `approved`.
- **One bad row (a typo'd category, a duplicate phone) does not stop the others** — every
  row's outcome (created, or skipped with the exact reason) prints at the end, and rows
  before a failure are already committed, not rolled back.

---

## 9. Testing the login gate itself

With `SKIP_ELIGIBILITY_CHECK=false` and the API server restarted:

- A phone number you created with `create_test_customer.py`/`import_test_customers.py`,
  status `approved` or `disbursed`, with a category → logs in, `can_create_listing: true`.
- Same, but `--category ""` (no trade category) → logs in, `can_create_listing: false`.
- Status `defaulted` or `rejected` → **rejected at `POST /auth/request-otp`**, no OTP sent
  at all (403, "This number isn't recognised, or isn't yet eligible.").
- A phone number nobody ever created → same 403, before any OTP send.

---

## 10. Firing the webhook triggers live

Both `create_test_customer.py` and `import_test_customers.py` print the `loan_id` for
every customer they create — use it directly:

```powershell
curl -X POST http://localhost:8000/webhooks/loan-approved `
  -H "X-Internal-Key: <INTERNAL_API_KEY from .env>" -H "Content-Type: application/json" `
  -d '{\"loan_id\": \"<the loan_id printed above>\"}'
```

(PowerShell needs backtick line-continuations and escaped quotes as shown — copy exactly,
or paste it all on one line.)

Watch the API server's own terminal — you should see a real `marketplace_invitations` row
get written and the stand-in SMS print with a real invitation code, for the phone number
you just created. Same idea for `POST /webhooks/loan-repaid` on a `disbursed` loan (this
is graduation.py's `record_loan_repaid()` — "as soon as it's repaid they'll send us
through API," now something you can actually trigger and watch).

Both webhooks require the `X-Internal-Key` header — a missing or wrong key gets a clean
401, nothing happens silently.

---

## 11. Quick reference — every script mentioned above

| Script | Purpose |
|---|---|
| `packages/data/generate_seed_data.py` | Bulk realistic seed data (500+ beneficiaries) — additive, never touches existing rows |
| `packages/data/export_seed_data.py` | Dumps the live database to CSV for review in Excel |
| `packages/data/create_test_customer.py` | One real customer at a time, via CLI args or prompts |
| `packages/data/import_test_customers.py` | Many real customers at once, from `test_customers_template.csv` |
| `packages/marketplace/smoke_test_*.py` | Each tests one piece of the module against the live database |
| `services/api/smoke_test_new_endpoints.py` | Real HTTP tests against a running server |

See `docs/Marketplace_Technical_Flow.md` for the code-level trace of what actually
happens, file by file, for every one of these flows.
