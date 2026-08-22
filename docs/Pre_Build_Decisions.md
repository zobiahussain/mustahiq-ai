# Pre-Build Decisions

Fourteen things our five pieces need to agree on before anyone opens an editor — so what
we each build actually fits together on integration day.

We wrote the architecture doc before writing any code, and it already told us we
wouldn't be able to lock it until we started building — too many dependencies only show
up in practice. That's still true. But on a first careful read of the SRS and
architecture docs, several things came up that aren't "we'll find out once we're
coding" — they're structural choices that **every** role's code depends on. If we each
guess differently on these, our pieces won't fit on integration day.

This is that list, sorted by who needs to weigh in. Shareable version (same content,
easier to read on a phone): https://claude.ai/code/artifact/67ee24ef-0334-4594-bc96-d109b68ee849

## Already decided, so it doesn't get re-litigated

**Embeddings run locally** (`sentence-transformers`, model `BAAI/bge-small-en-v1.5`, 384
dimensions) — Groq has no embeddings endpoint, confirmed against their docs directly.
Groq is generation-only in this system: assistant replies, JSON-mode field parsing,
match-reason text.

This fixes the vector column type in the schema at `vector(384)` — relevant for whoever's
finalizing the Supabase schema.

## Must settle before Day 1 — whole team

### 1. The API contract

**Plain language:** the architecture doc names exactly one endpoint out of the whole
system — `POST /profile`. Everything else both portals need to call is undefined. We
can't build two portals and three backend packages "in parallel," like the build order
assumes, if there's nothing shared to build against.

**Technical:** no OpenAPI spec, no request/response schemas, no error contract exists
anywhere yet. Proposed surface below — a starting point for Backend & Integration to
accept, cut, or extend, not a final spec imposed on that role.

**Profiles & Recommendations**

| Method | Path | Does | Fires |
|---|---|---|---|
| POST | `/profiles` | Create a beneficiary profile | 1, 2, 3 |
| GET | `/profiles/{id}` | Fetch a profile | |
| PATCH | `/profiles/{id}` | Update a profile | 3 |
| POST | `/profiles/parse` | Free text → structured fields | |
| GET | `/profiles/{id}/recommendations` | Matched programs, score, reason, source | |
| GET | `/profiles/{id}/alerts` | New marketplace matches found | 7 |

**Programs (department side)**

| Method | Path | Does | Fires |
|---|---|---|---|
| GET | `/programs` | List active programs | |
| POST | `/programs` | Create a new program | 5 |
| PATCH | `/programs/{id}` | Edit eligibility criteria | 6 |
| GET | `/programs/{id}/candidates` | Beneficiaries matched to this program | |

**Marketplace listings**

| Method | Path | Does | Fires |
|---|---|---|---|
| POST | `/listings` | Create a store listing | 4 |
| GET | `/listings/{id}` | Fetch a listing | |
| PATCH | `/listings/{id}` | Edit a listing | 4 |
| GET | `/listings/{id}/matches` | Ranked match results, premium marked | |
| POST | `/listings/{id}/premium` | Mark premium fee paid | 8 |
| GET | `/listings/{id}/ledger` | Fee & commitment history | |

**Assistant**

| Method | Path | Does |
|---|---|---|
| POST | `/assistant/chat` | Grounded reply with source citations |

Every route above assumes some notion of "who's calling" exists — that's item 3, not
solved here.

### 2. Do triggers run instantly, or in the background?

**Plain language:** when someone registers, do they wait on screen while the system
checks everything, or does the page load fast and results arrive a moment later?

**Technical:** SRS 11.1 implies registration blocks on results ("lands on a results
screen... right then") — synchronous. But triggers 5/6/13 re-scan *every* beneficiary
when a program changes — that can't reasonably hold an admin's HTTP request open, and no
queue/worker infra (Celery, Redis, etc.) is named anywhere for a single Render free-tier
service.

**Proposed default:** registration-time checks (eligibility scan, dedup, listing match)
run inline — small, fast, and the UI needs them immediately. Bulk re-scans (new/edited
program) run via FastAPI's built-in `BackgroundTasks` — no extra infra needed at this
scale.

### 3. What does "demo-scope auth" actually mean?

**Plain language:** who's allowed to see what — is there a login, and is a department's
view different from a beneficiary's?

**Technical:** Architecture's diagram says only the phrase "demo-scope auth." No login
flow, role distinction, or session strategy is specified anywhere.

**Proposed default:** one shared department credential (a single token) for the
department view; beneficiaries get a session tied to their profile id — no real account
system, matching everything else scoped to demo, not production.

### 4. What are the actual seven program domains?

**Plain language:** the requirements say Al-Khidmat runs seven kinds of programs, but
only name four as examples. We need all seven to build realistic demo data.

**Technical:** SRS §1 names education, healthcare, financial support, and vocational
training as examples of "seven distinct domain areas" — the other three are never
listed. Blocks Data Engineering's synthetic dataset and the requirement that scoring stay
"consistent across all seven program domains."

**Proposed default:** whoever has visibility into Al-Khidmat's actual program list should
confirm the real seven. If nobody does, we pick seven plausible domains ourselves and
label them clearly as illustrative for the demo — don't guess and present it as fact.

### 5. What happens when a duplicate is found?

**Plain language:** the system checks for duplicate registrations — but nothing says what
it actually does once it finds one.

**Technical:** trigger 2 runs RapidFuzz + vector similarity on every registration. No doc
specifies the resulting action — block, flag, merge?

**Proposed default:** flag it on the record and surface it in the department view for
manual review. Never auto-block or auto-merge — consistent with "the platform
recommends, it never decides" already stated for eligibility.

### 6. Are match reasons templated text, or a live LLM call?

**Plain language:** the "why you matched" text next to every result — is that written by
code from the score, or generated fresh by Groq each time?

**Technical:** if every reason is a live Groq call, the bulk re-scan triggers (5, 6, 13)
could burst dozens of calls at once — exactly the per-minute rate-limit risk already
named as demo risk #1 in the team docs, just not yet connected to this specific decision.

**Proposed default:** template-based by default — fill a sentence from the score
breakdown, no API call. Reserve live Groq generation for the on-demand assistant, where a
beneficiary asks a follow-up and volume is naturally low.

## Mine to decide — want your OK (marketplace & RAG)

### 7. How does marketplace matching pick between the 3 business models?

One shared embedding space with a classifier deciding supply-chain vs. joint-venture vs.
competitive-ranking, or a separate retrieval path per model. Affects how
`packages/marketplace` is structured internally.

### 8. How do we notify both sides of a match?

In-app only (an alert on next login), or email/SMS. In-app is far simpler for a hackathon
demo — leaning that way unless someone wants the extra polish.

### 9. Is a store listing created automatically, or by hand?

SRS 5.7 implies a manual form in the Marketplace Portal. The trigger table (trigger 3)
implies auto-creation the moment a profile has trade info. Working assumption:
auto-create a draft on profile save, let the portal edit/publish it — a guess, not yet a
decision.

### 10. What actually flips a venture from "grace period" to "earning"?

SRS wording implies a real earnings signal, but the system never processes live
payments — there's nothing to observe. Working assumption: it's purely time-based,
flipped by the same scheduled sweep that starts the donation commitment. A
simplification worth saying out loud rather than assuming silently.

## Watch item — consequence of a decision made

### 11. Render's free-tier RAM, with a local embedding model in the mix

Loading `sentence-transformers` (~130MB) into the same free-tier web service as FastAPI +
scikit-learn + XGBoost may be tight. If it bites: lazy-load the embedder as a singleton,
or split it into its own light process.

## Can wait — don't forget, don't block on

### 12. Fee figures and commitment cadence

Both docs use placeholders. Need real numbers before presenting, not before coding.

### 13. `consent_flags` on the beneficiary profile

The field exists in the schema; what consent it captures and what it gates was never
defined.

### 14. Registration fee: boolean flag, or ledger lookup?

`store_listings.registration_fee_paid` possibly duplicates what the Donation Ledger
already records — the boolean probably should be derived, not stored separately.
