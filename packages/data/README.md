# packages/data — Schema & Feature Support

**Owner:** Data Engineering & Feature Support role.

Supabase schema (tables, relationships, vector columns) as the single definition the API
and ML code share. Synthetic beneficiary/program datasets. Feature engineering (income
bands, family size, location clusters, prior assistance history).

## Eligibility-engine support

`FEATURE_CONTRACT.md`, `synthetic.py`, and `features.py` provide the shared Task 4.2/4.3
precondition for confidence scoring. They produce synthetic, hard-rule-surviving
profile/program examples and a fixed feature vector with explicit missingness signals.
They do not require a database, API, RAG, or frontend.

**Schema delivered** — `schema/al_khidmat_core_schema.sql` (11 tables: departments, staff
users, beneficiary profiles, programs, program criteria chunks, match records, the
potentially-eligible pool, verifications, applications, ranking cycles, duplicate flags)
and `schema/al_khidmat_marketplace_schema.sql` (9 tables, depends on the core schema's
`beneficiary_profiles` and `staff_users`). Run core before marketplace. Embedding columns
are `vector(768)` throughout — see the reconciliation note in the root `CLAUDE.md` before
changing that dimension anywhere.

**Depends on:** nothing — this must ship first.
**Depended on by:** every other package.
