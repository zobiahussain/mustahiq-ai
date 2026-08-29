# packages/dedup — Duplicate Detection

**Owner:** Similarity Matching, Duplicate Detection, Backend & Integration role.

**Changed:** exact CNIC match first, then fuzzy name/phone comparison via RapidFuzz — no
vector similarity anymore. `beneficiary_profiles` carries no embedding (confirmed in the
delivered schema), so the earlier "RapidFuzz + vector similarity on the wider profile"
approach no longer applies. Suspected pairs are written to `duplicate_flags` at
`status = 'pending'` for a staff queue — merging is always a manual decision, never
automatic. Owns trigger 2 (fires on profile creation).

**Depends on:** `packages/data` (schema).
**Depended on by:** `services/api`.
