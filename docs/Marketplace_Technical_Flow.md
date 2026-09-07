# Marketplace Technical Flow — code-level trace

Not another spec doc. `docs/Marketplace_Spec.md` says *what* the marketplace does and
*why*; this says *which file, which function, which table* for every real flow, in call
order — the thing you'd want open next to the debugger. Scoped to my module (RAG +
marketplace + `apps/marketplace-portal`) only.

Notation: `File.js → File.py:function() → SQL table` — an arrow is a real function call
or HTTP request, left to right, in the order it actually happens.

Line numbers below are current as of commit `2b29a19` (6 Sep 2026) — `services/api/main.py`
gets edited often enough that they *will* drift. Re-derive them anytime with:
`grep -n '^@app\.' services/api/main.py`.

---

## 1. Login (phone + one-time code)

```
App.jsx (phone step)
  → api.js:requestOtp(phone, testProfile?)
    → POST /auth/request-otp                                    [services/api/main.py:304]
      → auth.py:request_otp(phone, full_name?, district?, trade_category?)
        → SELECT beneficiary_profiles JOIN microfinance_loans   (the eligibility gate itself —
                                                                   Marketplace_Spec.md §2)
        → [only if SKIP_ELIGIBILITY_CHECK=true AND phone unmatched]
          auth.py:_auto_provision_test_beneficiary()
            → INSERT beneficiary_profiles, INSERT microfinance_loans
        → SELECT login_otps WHERE phone ORDER BY created_at DESC LIMIT 1
                                                                  — resend-cooldown check,
                                                                    added 6 Sep 2026
                                                                    (OTP_RESEND_COOLDOWN_
                                                                    SECONDS = 30) — Marketplace_
                                                                    Spec.md §2.1. Returns early
                                                                    with {otp_sent: false,
                                                                    reason: "cooldown",
                                                                    retry_after_seconds} if a
                                                                    code went out too recently
                                                                    for this number
        → INSERT login_otps (code_hash = sha256(code))
        → auth.py:_send_sms()  [stand-in — prints, no real provider wired up]
      ← {eligible, otp_sent, can_create_listing} or {eligible, otp_sent: false, reason: "cooldown", retry_after_seconds}

App.jsx (code step)
  → api.js:verifyOtp(phone, code)
    → POST /auth/verify-otp                                     [main.py:322]
      → auth.py:verify_otp(phone, code)
        → SELECT login_otps WHERE phone, consumed_at is null, expires_at > now()
        → compare sha256(code) to stored code_hash
        → UPDATE login_otps SET consumed_at = now()
        → INSERT/UPDATE beneficiary_app_accounts (ON CONFLICT DO UPDATE)
      ← {verified, beneficiary_id}
    → main.py:_issue_token(beneficiary_id)  — signs a JWT (JWT_SECRET, 30-day expiry)
  ← {token}                                  — stored in App.jsx state, sent as
                                                `Authorization: Bearer <token>` on every
                                                request after this
```

**Nothing above touches `packages/rag`** — login is pure Postgres + a JWT, no
embeddings, no Groq. This is also the one file (`auth.py`) that deliberately imports no
web framework — see its own docstring.

---

## 2. Landing on the dashboard

```
App.jsx
  → api.js:getMeContext(token)
    → GET /me/context                                           [main.py:331]
      → main.py:get_current_beneficiary(authorization)           — decodes + verifies the
                                                                     JWT (jwt.decode), 401 on
                                                                     missing/expired/invalid
      → auth.py:get_me_context(beneficiary_id)
        → SELECT beneficiary_profiles
        → SELECT microfinance_loans JOIN trade_categories (latest approved/disbursed)
      ← {full_name, district, cluster_id, trade_category, stated_purpose, can_create_listing}
```

---

## 3. Creating a listing (voice-first, two screens)

Rebuilt 5 Sep 2026 from an earlier five-card tap-through form — see
Marketplace_Spec.md §3 for why. `draft_full_listing_from_speech()` (one richer LLM call)
replaced the old `enrich_listing_text()` as the primary path; the older function is kept
working (still importable) but nothing in the shipped UI calls it anymore.

```
Screen 1 (voice, optional)
  ListingWizard.jsx → api.js:transcribeAudio(token, audioBlob)
    → POST /listing/transcribe                                  [main.py:474]
      → groq_client.py:transcribe_audio()  — Groq's hosted Whisper
  ← {text}   — drops into the SAME editable box typing would have

Screen 1 → screen 2 transition (the one LLM call, drafts the WHOLE listing)
  ListingWizard.jsx → api.js:draftListing(token, rawText)
    → POST /listing/draft                                       [main.py:345]
      → create_listing.py:draft_full_listing_from_speech(beneficiary_id, raw_text)
        → create_listing.py:_fetch_beneficiary_context()         — district/cluster/category,
                                                                     never re-asked
        → SELECT trade_categories (category name for the prompt)
        → groq_client.py:chat_json(FULL_DRAFT_PROMPT)             — Groq, JSON-mode, ONE call
      ← {role, seeking_inputs/workers/partner/work, business_name,
          product_or_service_en, product_or_service_original, skills_en,
          is_women_led, monthly_capacity, price_range}
                                                                    — every field shown editable,
                                                                      nothing saved yet.
                                                                      is_remote_capable,
                                                                      output_is_physical, and the
                                                                      three travel-willingness
                                                                      flags are NEVER in this
                                                                      response — ListingWizard.jsx
                                                                      asks those directly on the
                                                                      same review screen, no
                                                                      AI-suggested default
                                                                      (Marketplace_Spec.md §3.1)

Screen 2 confirm
  ListingWizard.jsx → api.js:saveListing(token, payload)
    → POST /listing                                              [main.py:377]
      → create_listing.py:save_listing(beneficiary_id, **payload)
        → create_listing.py:_fetch_beneficiary_context()          — re-derives district/
                                                                      cluster/category
                                                                      server-side, never
                                                                      trusts the request body
        → SELECT count(*) FROM store_listings                     — is_first_listing check
        → embeddings.py:embed_text(text_to_embed)                 — 768-dim vector, local,
                                                                      CPU (BAAI/bge-base-en)
        → INSERT store_listings (... , embedding, matches_computed_at=null)
        → INSERT listing_participants (role='owner', status='confirmed')
        → [if is_first_listing] INSERT graduation_events (event_type='business_established')
      ← listing_id
      → background_tasks.add_task(match_and_notify, listing_id)   — SCHEDULED, not awaited —
                                                                      changed 6 Sep 2026, see
                                                                      below
  ← {listing_id, matches_pending: true}                            — returns as soon as
                                                                      save_listing() is done;
                                                                      the frontend does NOT get
                                                                      matches in this response
                                                                      anymore
```

### 3.1 Why match_and_notify() moved off the request, and how the frontend finds out

Before 6 Sep 2026, `match_and_notify(listing_id)` ran INLINE, in the same request as
`POST /listing`, and the response carried the finished `matches` list. That meant the
HTTP response was blocked on `reasoning.py:add_reasons()` — ONE Groq call PER surviving
match, up to 8-10 sequential calls for a listing with several matches — which is why
saving a listing could take a minute or two with nothing to show for it.

Now `match_and_notify()` runs as a FastAPI `BackgroundTasks` job, scheduled by
`listing_save()` right after `save_listing()` returns, executing AFTER the HTTP response
is already sent:

```
matching_pipeline.py:match_and_notify(listing_id)            — runs in the background,
                                                                  off the request
  → matching.py:_fetch_listing(cur, listing_id)
  → matching.py:find_matches(listing_id)                       — see §5 below
  → reasoning.py:add_reasons(source, matches)                  — Groq, ONE call per match
                                                                    that survives (not every
                                                                    candidate scored along the
                                                                    way)
  → persist.py:persist_matches(listing_id, matches)            — UPSERT marketplace_matches
  → [for each NEW match only -- is_new from persist_matches]
    → logistics gate → logistics.py:find_logistics_for_route()  — if goods/person are
                                                                     moving cross-cluster
    → notify.py:notify_match()  ×2                               — once per side
  → persist.py (via matching_pipeline.py:_mark_matches_computed)
    → UPDATE store_listings SET matches_computed_at = now()      — ALWAYS runs, even on a
                                                                     hard failure partway
                                                                     through (try/finally) —
                                                                     see below for why
```

`migrations/0001_matches_computed_at.sql` added the column this depends on: `null` means
"still running or never triggered," a real timestamp means done. Wrapped in `try/finally`
specifically so a mid-run failure (Groq rate-limited, say) still flips the signal — a
listing stuck on "finding matches" forever because one LLM call failed would be worse
than surfacing a possibly-incomplete real result.

**Why `BackgroundTasks` and not a rewrite to `asyncpg`/`httpx`** (real tradeoff, not
obvious): FastAPI supports true non-blocking `async def` handlers, but every DB call in
this codebase goes through `psycopg2` (blocking) and Groq's sync client — a blocking call
inside an `async def` still blocks the single event loop exactly as badly as in a sync
`def`. Getting real concurrency would mean replacing `psycopg2`/`requests` everywhere,
not just here — a much bigger change for a benefit this small a service doesn't need yet.
`BackgroundTasks` runs the existing sync code, unchanged, in a thread pool after the
response is sent — solving the actual problem (the client waiting on work it didn't need
to see finish) without that rewrite.

---

## 4. Viewing matches (polled while pending, a plain read once done)

Changed 6 Sep 2026 alongside §3.1's backgrounding: this endpoint now has to distinguish
"matching hasn't run yet" from "matching ran and found nothing" — both used to look like
an empty list. `MatchResults.jsx` polls it every 3 seconds while `pending: true`.

```
MatchResults.jsx (on mount, and every 3s while pending)
  → api.js:getListingMatches(token, listingId)
    → GET /listing/{listing_id}/matches                          [main.py:421]
      → persist.py:is_matches_pending(listing_id)                 — SELECT matches_computed_at;
                                                                      null → pending, caller
                                                                      404s if the listing
                                                                      doesn't exist at all
      → [if pending] ← {matches: [], pending: true, no_match_explanation: null}
      → [if not pending]
        → persist.py:get_stored_matches(listing_id)                — pure SELECT, NO fresh
                                                                        embeddings, NO fresh
                                                                        Groq calls (already
                                                                        computed by the
                                                                        background task)
          → involvement.py:get_other_involvements_batch()           — §9.4 transparency, 2
                                                                        queries total for the
                                                                        whole page (not 2×N)
        → [only if matches is empty] match_diagnostics.py:explain_no_matches(listing_id)
                                                                      — see §5.1 below; NOT
                                                                        computed when matches
                                                                        were actually found
        ← {matches: [...], pending: false, no_match_explanation: [...] or null}

Dismiss button
  → api.js:dismissMatch(token, matchId, dismissingListingId)
    → POST /matches/{match_id}/dismiss                            [main.py:452]
      → persist.py:dismiss_match(match_id, dismissing_listing_id)
        → UPDATE marketplace_matches SET status='dismissed'
        → UPDATE store_listings SET open_request_count = open_request_count - 1 (both sides)

Connect button (not yet in the UI — API only, see §7)
  → POST /matches/{match_id}/connect                              [main.py:592]
      → graduation.py:confirm_match_connection(match_id, beneficiary_id)
```

---

## 5. Matching logic, unpacked (what `find_matches()` actually does)

```
matching.py:find_matches(listing_id, limit=10)
  → matching.py:_fetch_listing(cur, listing_id)                   — the SOURCE listing's full
                                                                      row, including willingness
                                                                      flags and trade_category_id
  → ANY combination of these 5 can fire, independently, per source listing --
    not "pick one": each condition is checked separately, so a listing with
    multiple seeking_* flags set queries multiple models in one find_matches() call.
      source["seeking_inputs"]        → _search_supply_chain_suppliers(cur, source, limit)
      source["role"] == "supplier"    → _search_supply_chain_producers(cur, source, limit)
      source["seeking_workers"]       → _search_employment_workers(cur, source, limit)
      source["seeking_work"]          → _search_employment_businesses(cur, source, limit)
      source["seeking_partner"]       → _search_joint_venture(cur, source, limit)
    Each does, in ONE SQL query (never fetch-then-filter in Python):
      1. complementary role filter        (WHERE clause)
      2. distance-eligibility filter       (WHERE clause, skipped per §3.3's two gates)
      3. rate-limit filter                 (open_request_count < max_open_requests)
      4. quality floor                     (embedding <=> vec <= 1 - MIN_SIMILARITY, i.e.
                                              similarity >= 0.25 — Marketplace_Spec.md §5.3.
                                              Employment queries ALSO require:
                                              trade_category_id = source's, OR similarity
                                              >= EMPLOYMENT_STRONG_SIMILARITY (0.70))
      5. vector similarity                 (ORDER BY embedding <=> %(vec)s::vector, id — the
                                              trailing `, id` added 6 Sep 2026: with enough
                                              template-duplicated seed listings sharing the
                                              exact same embedding, ties on distance alone
                                              gave Postgres no guaranteed order, so the SAME
                                              query on UNCHANGED data could return a
                                              DIFFERENT top-N between two calls — caught by
                                              smoke_test_persist.py failing intermittently.
                                              `, id` makes ordering deterministic)
  → [Python, after all SQL is done] proximity.py:proximity_multiplier()  — per candidate:
                                          same cluster ×1.00 / adjacent district ×0.85 /
                                          same province ×0.70 / elsewhere ×0.50
  ← all candidates pooled, sorted by final_score (similarity × proximity) desc, top `limit`
```

### 5.1 When find_matches() genuinely returns nothing — match_diagnostics.py

Added 6 Sep 2026 — an empty result used to just be an empty result; now the API can say
*why*, using real numbers from the same filters above, not a Groq call:

```
match_diagnostics.py:explain_no_matches(listing_id)   — only called from GET
                                                          /listing/{id}/matches when
                                                          get_stored_matches() came back
                                                          empty AND pending is false
  → matching.py:_fetch_listing()                        — same source row
  → for each active seeking flag, match_diagnostics.py:_funnel()
      re-runs that direction's filter as 3-4 progressively stricter COUNT(*) queries:
        total          — role/seeking + active + availability + rate-limit, no geography yet
        after_geo       — + distance-eligibility clause
        after_floor     — + quality floor
        after_strong    — (employment only) + same-category-or-strong-similarity gate
      → match_diagnostics.py:_reason_for() picks the template matching whichever
        count FIRST hit zero, with the real count filled in (e.g. "3 businesses need
        what you offer, but none are near you or willing to deliver")
  ← [{"direction": "employment_hiring", "reason_en": "...", "reason_ur": "..."}, ...]
```

Templated, not a Groq call, by design — every number is a direct SQL count, no ambiguity
to resolve, and it deliberately avoids adding a second LLM dependency on top of the one
already in `reasoning.py:add_reasons()`.

---

## 6. Search / browse (deliberately a different code path — see §5.4)

```
Search.jsx (loads on mount, not on submit — Marketplace_Spec.md §5.4 "browse without
             typing a query first")
  → api.js:searchListings(token, filters)
    → GET /listings/search                                        [main.py:526]
      → search.py:search_listings(query_text?, trade_category?, role?, district?, ...)
        → [if query_text] embeddings.py:embed_text(query_text)
        → ONE SQL query — NO proximity filter, NO willingness check, NO quality floor
                             (unfiltered, pull-driven — §5.4. The floor added in §5 above
                             gates automatic MATCHING specifically; search stays
                             deliberately wide-open, same reasoning as the willingness
                             flags it also skips)
        → involvement.py:get_other_involvements_batch()             — same §9.4 signal as
                                                                        match results
      ← [{id, business_name, product_or_service_en, ..., other_involvements}]
```

---

## 7. Zakat graduation triggers (§11.1) — five real endpoints, mostly not yet in the UI

```
POST /donations                    [main.py:586] → graduation.py:record_donation()
POST /matches/{id}/connect         [main.py:592] → graduation.py:confirm_match_connection()
POST /me/no-longer-seeking         [main.py:649] → graduation.py:record_no_longer_seeking_assistance()
POST /webhooks/loan-approved       [main.py:656] → lifecycle.py:send_invitation_if_eligible()
POST /webhooks/loan-repaid         [main.py:669] → graduation.py:record_loan_repaid()
```

The last two are **webhook targets**, not beneficiary actions — gated by
`require_internal_key()` (shared-secret `X-Internal-Key` header), not the JWT. They're
meant to be called by Al-Khidmat's own loan-servicing system whenever a `microfinance_loans`
row is written or its status changes to `disbursed`/repaid — nothing in this codebase calls
them automatically yet except test scripts standing in for that real caller.

`business_established` is the one graduation event with no dedicated endpoint — it fires
inline inside `create_listing.py:save_listing()` (see §3 above), since "first listing ever"
is a signal that already exists at that exact moment.

---

### 7.1 Chat and contact reveal — two-stage, added 5 Sep 2026

Direct feedback: "there should be a chat within the marketplace... as soon as you feel
like you already established something, then they can call." Two stages, in
`messaging.py`:

```
Stage 1 -- open the moment a match exists, no phone number involved
Chat.jsx → api.js:sendMatchMessage(token, matchId, body)
  → POST /matches/{match_id}/messages                             [main.py:613]
    → messaging.py:send_message(match_id, beneficiary_id, body)
      → graduation.py:_is_party_to_match()                          — reused, not
                                                                        duplicated (same
                                                                        check
                                                                        confirm_match_
                                                                        connection() uses)
      → INSERT match_messages
  ← {message_id}

Chat.jsx → api.js:getMatchMessages(token, matchId)
  → GET /matches/{match_id}/messages                               [main.py:627]
    → messaging.py:get_messages(match_id, beneficiary_id)
      ← [{id, sender_id, body, sent_at}, ...]

Stage 2 -- only after EITHER party marks the match connected
  (POST /matches/{id}/connect, §7 above — no new endpoint needed for the trigger)
Chat.jsx → api.js:getMatchContact(token, matchId)
  → GET /matches/{match_id}/contact                                [main.py:635]
    → messaging.py:get_contact_info(match_id, beneficiary_id)
      → SELECT full_name, phone for the OTHER party of THIS match only —
        never a general beneficiary lookup
      ← {full_name, phone} or null (404) if not connected yet, or caller isn't a party
```

Deliberately not threshold-based ("after 5 messages," say) — connection is an explicit
action either party takes, same "the system does not decide" principle
Marketplace_Spec.md §9.3 already uses for availability.

---

### 7.2 Migrations — real schema changes, added 6 Sep 2026

`packages/data/migrations/` + `run_migrations.py` replace hand-applying SQL directly
against the live database and separately remembering to update `packages/data/schema/*.sql`
to match — see `migrations/README.md` for the full reasoning. First real migration:

```
run_migrations.py
  → CREATE TABLE IF NOT EXISTS schema_migrations (id text primary key, applied_at ...)
  → for each migrations/*.sql file NOT already in schema_migrations, in filename order:
      → runs the file's SQL, in its own transaction (a failure rolls back cleanly,
        stops the run, everything before it stays recorded as applied)
      → INSERT schema_migrations (id = filename)

migrations/0001_matches_computed_at.sql
  → ALTER TABLE store_listings ADD COLUMN IF NOT EXISTS matches_computed_at timestamptz
                                                          — backs §3.1's async signal
```

Run it with `cd packages/data && ../rag/.venv/Scripts/python.exe run_migrations.py` —
safe to run repeatedly, already-applied migrations are skipped.

---

## 8. Ventures and logistics (self-contained, no matching-pipeline involvement)

```
POST /ventures/form                [main.py:688]
  → ventures.py:form_venture(beneficiary_id, venture_listing_id, parent_listing_ids)
    → verify caller owns ≥1 parent (listing_participants)
    → INSERT venture_lineage (per parent)
    → INSERT listing_participants (each parent's owner(s), ON CONFLICT DO NOTHING)
    → UPDATE store_listings SET availability='committed' (each parent)

POST /listing/{id}/availability    [main.py:572]
  → listings.py:set_availability(beneficiary_id, listing_id, availability)
    → ownership check (listing_participants)
    → UPDATE store_listings SET availability

POST /logistics/routes             [main.py:706]
  → logistics.py:add_logistics_route()
    → INSERT logistics_routes (rejects non-logistics-role listings)
```

---

## 9. Reporting and scheduled housekeeping (no beneficiary involved)

```
GET /reports/impact                [main.py:719, gated by require_internal_key()]
  → reporting.py:get_impact_report()  — one SQL query, schema reference query F verbatim

Not wired to any endpoint yet -- called directly (by a script, or eventually Render cron):
  lifecycle.py:expire_stale_matches()                  — 7-day match expiry (§7)
  lifecycle.py:expire_stale_listings()                 — 6-month listing expiry (§10)
  lifecycle.py:deactivate_listings_for_defaulted_loan() — schema ref query J
```

---

## The two packages everything above actually depends on

- **`packages/rag`** — `embeddings.py` (local, CPU, `BAAI/bge-base-en-v1.5`, 768-dim,
  lazy-singleton-loaded, warmed at FastAPI startup — see `services/api/main.py`'s
  `lifespan`) and `groq_client.py` (`chat_json()` for the enrichment/reasoning calls,
  `transcribe_audio()` for voice input — both go through the one usage-logging wrapper
  CLAUDE.md describes).
- **Postgres connections** — every function above opens its own `psycopg2.connect()`
  call; nothing is pooled yet except where a caller explicitly passes an already-open
  `conn` (see `involvement.py`'s batch functions). `DATABASE_URL` switched from
  Supabase's direct (IPv6) host to the **Session Pooler** connection string on 6 Sep
  2026 (Settings → Database → Connection string → Session pooler, in the Supabase
  dashboard) — confirmed directly, not assumed: fresh-connection time dropped from
  ~9.6s (the 5 Sep 2026 finding in `involvement.py`'s docstring) to 1.5-2.5s, a real
  4-6x improvement from resolving over IPv4 instead of IPv6 on this network. The
  batching work `involvement.py` already did (collapsing many connections into a
  handful) is unaffected and still worth keeping — this fix lowers the cost of each
  connection, batching lowers how many get opened; the two are complementary, not
  alternatives.
- **Migrations** — see §7.2. `packages/data/schema/*.sql` are still the readable, current
  snapshot; `packages/data/migrations/` is where every change from 6 Sep 2026 onward is
  recorded.
