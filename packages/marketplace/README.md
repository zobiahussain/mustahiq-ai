# packages/marketplace — Beneficiary Marketplace

**Owner:** Marketplace, Business Matching & Shared RAG Layer role.

**Full spec:** [docs/Marketplace_Spec.md](../../docs/Marketplace_Spec.md) — read that
before building anything here, it is the authoritative, detailed source.

Runs on the beneficiary app, **no staff involvement** — listings are created by a
conversational assistant (voice or text), matching is automatic, both parties are
notified directly by SMS and email. A beneficiary joins only after applying for and
receiving a microfinance loan; this is downstream of a loan choice, never of an
eligibility match.

**3 business models** (not the old 3 — "competitive ranking" is gone):
1. Supply chain — a supplier of inputs matched to a producer who needs them
2. Employment — a business needing a skill matched to a beneficiary who has it
3. Joint venture — two owners pooling into one shared business

Plus logistics (rickshaw/three-wheeler operators) as a fourth participant role, not a
fourth model — makes cross-cluster matches workable.

**Matching logic:** complementary-role filter → distance-eligibility filter (delivery
willingness for goods, relocation willingness for employment) → vector similarity over
listing text → proximity re-weighting (same cluster ×1.00, adjacent district ×0.85, same
province ×0.70, elsewhere ×0.50). Always searches the whole pool, not just new listings —
this is what makes a Monday listing and a Friday listing still find each other.

**No fees, anywhere.** Registration fee, premium ranking, and donation-commitment
schedule from the earlier revision are all gone — premium ranking was explicitly
considered and rejected (charging for visibility means the poorest are seen least). The
only money flow is a voluntary, no-schedule donation once a business is established.
Track "zakat graduation" (mustahiq → donor) as a reportable metric instead — see spec §11.

**Triggers I own:** 7 (listing created/edited → match + notify both parties by SMS/email),
9 (daily → expire matches after 7 days unanswered, expire listings after 6 months
unconfirmed) — see
[docs/Team_Work_Division.md §3](../../docs/Team_Work_Division.md#3-trigger-ownership).
Trigger 9 kept its number from the old revision but changed meaning entirely — it used to
be a grace-period/donation sweep, now it's marketplace housekeeping.

**Depends on:** `packages/data` (schema — `schema/al_khidmat_marketplace_schema.sql`,
depends on `beneficiary_profiles`/`staff_users` from the core schema), `packages/rag`
(listing-text embedding), `services/api` (deployment/API conventions).
**Depended on by:** `apps/marketplace-portal`.
