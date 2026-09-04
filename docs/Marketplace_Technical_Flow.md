# Marketplace Technical Flow — code-level trace

Not another spec doc. `docs/Marketplace_Spec.md` says *what* the marketplace does and
*why*; this says *which file, which function, which table* for every real flow, in call
order — the thing you'd want open next to the debugger. Scoped to my module (RAG +
marketplace + `apps/marketplace-portal`) only.

Notation: `File.js → File.py:function() → SQL table` — an arrow is a real function call
or HTTP request, left to right, in the order it actually happens.

Line numbers below are current as of commit `5d9d091` (5 Sep 2026) — `services/api/main.py`
gets edited often enough that they *will* drift. Re-derive them anytime with:
`grep -n '^@app\.' services/api/main.py`.

---

## 1. Login (phone + one-time code)

```
App.jsx (phone step)
  → api.js:requestOtp(phone, testProfile?)
    → POST /auth/request-otp                                    [services/api/main.py:301]
      → auth.py:request_otp(phone, full_name?, district?, trade_category?)
        → SELECT beneficiary_profiles JOIN microfinance_loans   (the eligibility gate itself —
                                                                   Marketplace_Spec.md §2)
        → [only if SKIP_ELIGIBILITY_CHECK=true AND phone unmatched]
          auth.py:_auto_provision_test_beneficiary()
            → INSERT beneficiary_profiles, INSERT microfinance_loans
        → INSERT login_otps (code_hash = sha256(code))
        → auth.py:_send_sms()  [stand-in — prints, no real provider wired up]
      ← {eligible, otp_sent, can_create_listing}

App.jsx (code step)
  → api.js:verifyOtp(phone, code)
    → POST /auth/verify-otp                                     [main.py:319]
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
    → GET /me/context                                           [main.py:328]
      → main.py:get_current_beneficiary(authorization)           — decodes + verifies the
                                                                     JWT (jwt.decode), 401 on
                                                                     missing/expired/invalid
      → auth.py:get_me_context(beneficiary_id)
        → SELECT beneficiary_profiles
        → SELECT microfinance_loans JOIN trade_categories (latest approved/disbursed)
      ← {full_name, district, cluster_id, trade_category, stated_purpose, can_create_listing}
```

---

## 3. Creating a listing (5-card wizard)

```
Card 3 (voice, optional)
  ListingWizard.jsx → api.js:transcribeAudio(token, audioBlob)
    → POST /listing/transcribe                                  [main.py:397]
      → groq_client.py:transcribe_audio()  — Groq's hosted Whisper
  ← {text}   — drops into the SAME editable box typing would have

Card 3 → card 4 transition (the one LLM call)
  ListingWizard.jsx → api.js:extractListingText(token, rawText)
    → POST /listing/extract                                     [main.py:333]
      → create_listing.py:enrich_listing_text(beneficiary_id, raw_text)
        → create_listing.py:_fetch_beneficiary_context()         — district/cluster/category,
                                                                     never re-asked
        → SELECT trade_categories (category name for the prompt)
        → groq_client.py:chat_json(ENRICHMENT_PROMPT)             — Groq, JSON-mode, ONE call
      ← {product_or_service_en, product_or_service_original, skills_en}
                                                                    — shown editable, nothing
                                                                      saved yet

Card 5 confirm
  ListingWizard.jsx → api.js:saveListing(token, payload)
    → POST /listing                                              [main.py:341]
      → create_listing.py:save_listing(beneficiary_id, **payload)
        → create_listing.py:_fetch_beneficiary_context()          — re-derives district/
                                                                      cluster/category
                                                                      server-side, never
                                                                      trusts the request body
        → SELECT count(*) FROM store_listings                     — is_first_listing check
        → embeddings.py:embed_text(text_to_embed)                 — 768-dim vector, local,
                                                                      CPU (BAAI/bge-base-en)
        → INSERT store_listings (... , embedding)
        → INSERT listing_participants (role='owner', status='confirmed')
        → [if is_first_listing] INSERT graduation_events (event_type='business_established')
      ← listing_id
      → matching_pipeline.py:match_and_notify(listing_id)         — SAME REQUEST, automatic
                                                                      (Marketplace_Spec.md §5.2,
                                                                      the delayed-match fix)
        → matching.py:find_matches(listing_id)                    — see §5 below for the
                                                                      full breakdown
        → reasoning.py:add_reasons(source, matches)                — Groq, ONE call per match
                                                                      that survives to the final
                                                                      list (not every candidate
                                                                      scored along the way).
                                                                      This IS genuinely
                                                                      LLM-written text, unlike
                                                                      the eligibility side's
                                                                      templated/rule-based
                                                                      reasons — no audit trail
                                                                      needed for "these two
                                                                      businesses might suit
                                                                      each other" (see
                                                                      reasoning.py's docstring)
        → persist.py:persist_matches(listing_id, matches)         — UPSERT marketplace_matches,
                                                                      increments
                                                                      open_request_count on
                                                                      genuinely NEW matches only
        → [for each NEW match only -- is_new from persist_matches, never re-fires
           on a re-score of an already-known pair]
          → matching_pipeline.py logistics gate                    — logistics.py:
                                                                      find_logistics_for_route()
                                                                      if goods/person are moving
                                                                      cross-cluster (checks BOTH
                                                                      output_is_physical and
                                                                      is_remote_capable
                                                                      independently — §3.3)
          → notify.py:notify_match()  ×2                            — once for each side (source
                                                                      AND the matched listing's
                                                                      owner) — SMS stand-in,
                                                                      writes a real
                                                                      `notifications` row
                                                                      regardless; skipped for a
                                                                      side with no single owner
                                                                      (a venture listing)
      ← {listing_id, matches}
```

---

## 4. Viewing matches (a plain read, no recomputation)

```
MatchResults.jsx
  → api.js:getListingMatches(token, listingId)
    → GET /listing/{listing_id}/matches                          [main.py:361]
      → persist.py:get_stored_matches(listing_id)                 — pure SELECT, NO fresh
                                                                      embeddings, NO fresh
                                                                      Groq calls (already
                                                                      computed at creation)
        → involvement.py:get_other_involvements_batch()           — §9.4 transparency, 2
                                                                      queries total for the
                                                                      whole page (not 2×N)
      ← [{id, match_model, final_score, proximity_label, reason,
           other_id, business_name, role, other_involvements, ...}]

Dismiss button
  → api.js:dismissMatch(token, matchId, dismissingListingId)
    → POST /matches/{match_id}/dismiss                            [main.py:375]
      → persist.py:dismiss_match(match_id, dismissing_listing_id)
        → UPDATE marketplace_matches SET status='dismissed'
        → UPDATE store_listings SET open_request_count = open_request_count - 1 (both sides)

Connect button (not yet in the UI — API only, see §7)
  → POST /matches/{match_id}/connect                              [main.py:484]
      → graduation.py:confirm_match_connection(match_id, beneficiary_id)
```

---

## 5. Matching logic, unpacked (what `find_matches()` actually does)

```
matching.py:find_matches(listing_id, limit=10)
  → matching.py:_fetch_listing(cur, listing_id)                   — the SOURCE listing's full
                                                                      row, including willingness
                                                                      flags
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
      4. vector similarity                 (embedding <=> %(vec)s::vector, ORDER BY)
  → [Python, after all SQL is done] proximity.py:proximity_multiplier()  — per candidate:
                                          same cluster ×1.00 / adjacent district ×0.85 /
                                          same province ×0.70 / elsewhere ×0.50
  ← all candidates pooled, sorted by final_score (similarity × proximity) desc, top `limit`
```

---

## 6. Search / browse (deliberately a different code path — see §5.3)

```
Search.jsx (loads on mount, not on submit — Marketplace_Spec.md §5.3 "browse without
             typing a query first")
  → api.js:searchListings(token, filters)
    → GET /listings/search                                        [main.py:418]
      → search.py:search_listings(query_text?, trade_category?, role?, district?, ...)
        → [if query_text] embeddings.py:embed_text(query_text)
        → ONE SQL query — NO proximity filter, NO willingness check (unfiltered, pull-driven,
                                                                        §5.3)
        → involvement.py:get_other_involvements_batch()             — same §9.4 signal as
                                                                        match results
      ← [{id, business_name, product_or_service_en, ..., other_involvements}]
```

---

## 7. Zakat graduation triggers (§11.1) — five real endpoints, mostly not yet in the UI

```
POST /donations                    [main.py:478] → graduation.py:record_donation()
POST /matches/{id}/connect         [main.py:484] → graduation.py:confirm_match_connection()
POST /me/no-longer-seeking         [main.py:498] → graduation.py:record_no_longer_seeking_assistance()
POST /webhooks/loan-approved       [main.py:505] → lifecycle.py:send_invitation_if_eligible()
POST /webhooks/loan-repaid         [main.py:518] → graduation.py:record_loan_repaid()
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

## 8. Ventures and logistics (self-contained, no matching-pipeline involvement)

```
POST /ventures/form                [main.py:537]
  → ventures.py:form_venture(beneficiary_id, venture_listing_id, parent_listing_ids)
    → verify caller owns ≥1 parent (listing_participants)
    → INSERT venture_lineage (per parent)
    → INSERT listing_participants (each parent's owner(s), ON CONFLICT DO NOTHING)
    → UPDATE store_listings SET availability='committed' (each parent)

POST /listing/{id}/availability    [main.py:464]
  → listings.py:set_availability(beneficiary_id, listing_id, availability)
    → ownership check (listing_participants)
    → UPDATE store_listings SET availability

POST /logistics/routes             [main.py:555]
  → logistics.py:add_logistics_route()
    → INSERT logistics_routes (rejects non-logistics-role listings)
```

---

## 9. Reporting and scheduled housekeeping (no beneficiary involved)

```
GET /reports/impact                [main.py:568, gated by require_internal_key()]
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
  `conn` (see `involvement.py`'s batch functions). `DATABASE_URL` is Supabase's direct
  (IPv6) host — see the 5 Sep 2026 performance fix in `involvement.py`'s docstring for
  why that matters and what's already been done about it.
