# Prioritization Module Implementation Plan

## Summary

Create `packages/eligibility/prioritization.py` and `packages/eligibility/tests/test_prioritization.py`.

This is the pure, deterministic third eligibility stage: rank already verified candidates within one program. It must not call discovery, hard-rule evaluation, XGBoost, databases, APIs, RAG, or scheduling code.

## 1) Scope and non-goals

- Input candidates represent verified applications only. The caller has already excluded stale or non-eligible verification outcomes.
- The module has no program, department, database, workflow, or verification-freshness knowledge.
- It must never accept, derive, return, or weight `entry_path`.
- Discovery confidence, raw intake-profile values, hard-rule status, and XGBoost are excluded.
- No existing eligibility/data modules are changed.

## 2) Candidate input design

Use strict Pydantic models with `extra="forbid"`, matching the existing eligibility contracts.

`VerifiedCandidate` fields:

| Field | Type | Required | Source |
|---|---|---:|---|
| `candidate_id` | UUID | Yes | `applications.id` |
| `cycles_waited` | non-negative integer | Yes | `applications.cycles_waited` |
| `verified_income` | non-negative Decimal or `None` | No | `verifications.verified_income` |
| `verified_household_size` | non-negative integer or `None` | No | `verifications.verified_household_size` |
| `urgency_level` | `low`, `medium`, `high`, `critical`, or `None` | No | `verifications.urgency_level` |
| `dependents` | non-negative integer or `None` | No | verified `program_specific_data` |
| `has_disability` | boolean or `None` | No | verified `program_specific_data` |
| `chronic_illness_flag` | boolean or `None` | No | verified `program_specific_data` |
| `prior_assistance_count` | non-negative integer or `None` | No | verified `program_specific_data` |
| `school_age_children` | non-negative integer or `None` | No | verified `program_specific_data` |

The caller/adaptor may extract the supplemental fields from `verifications.program_specific_data`, but only when staff recorded them as verified facts. It must never copy them from the original beneficiary intake profile.

All optional missing factors contribute `0` except the two inverted factors defined in section 4. Candidates are never excluded solely because an optional verified fact is missing.

## 3) Weight validation rules

`rank_candidates` accepts a non-empty mapping of factor name to non-negative numeric weight.

Supported factor names, in this canonical output order:

1. `income_inverse`
2. `household_size`
3. `urgency`
4. `dependents`
5. `disability`
6. `chronic_illness`
7. `no_prior_assistance`
8. `school_age_children`
9. `cycles_waited`

Rules:

- `entry_path` is explicitly rejected with `ValueError`, even before generic unsupported-key validation.
- Any unsupported factor key raises `ValueError`.
- Boolean values, negative values, non-finite values, and non-numeric weights raise `ValueError`.
- Weights must total `1.0`, allowing a maximum floating-point transport tolerance of `0.000001`; otherwise raise `ValueError`.
- For a total within that tolerance, normalize weights by the supplied total before calculating contributions. This only removes JSON/float representation drift and does not permit arbitrary raw totals.
- Every result’s breakdown includes every configured factor, in canonical factor order, including factors whose contribution is zero.

Requiring normalized weights makes every final score interpretable on a `0` to `1` scale and comparable across programs, even when programs choose different factor combinations.

## 4) Scoring methodology per factor

All raw factor scores are bounded between `0` and `1`. Each breakdown value is:

`normalized factor score × normalized program weight`

The overall priority score is the float sum of the visible factor contributions. Do not round during calculation.

### Numeric type constraint

All internal arithmetic uses `float`: raw-factor scores, numeric caps, weight normalization, per-factor contributions, and the overall sum. Before arithmetic, `verified_income` is converted from its input `Decimal` to `float`; integer candidate values are likewise used as floats for their factor calculations.

`Decimal` is used only at the final `RankedCandidate` output boundary. Convert every float contribution and the final float overall score using `Decimal(str(value))`, never `Decimal(value)`, to avoid binary floating-point artifacts. Tests comparing the sum of Decimal breakdown values with the Decimal overall score use a maximum difference of `Decimal("0.000000001")`.

| Factor | Raw-factor score |
|---|---|
| `income_inverse` | If present: `1 - min(verified_income / 100000, 1)`. Lower verified income produces higher need. |
| `household_size` | Missing: `0`. Otherwise `min(verified_household_size / 10, 1)`. |
| `urgency` | Missing: `0`. `low = 0.25`, `medium = 0.50`, `high = 0.75`, `critical = 1.00`. |
| `dependents` | Missing: `0`. Otherwise `min(dependents / 10, 1)`. |
| `disability` | `True = 1`, `False` or missing = `0`. |
| `chronic_illness` | `True = 1`, `False` or missing = `0`. |
| `no_prior_assistance` | If present: `1 - min(prior_assistance_count / 5, 1)`. Zero confirmed prior assistance receives `1`. |
| `school_age_children` | Missing: `0`. Otherwise `min(school_age_children / 5, 1)`. |
| `cycles_waited` | `min(cycles_waited / 6, 1)`. This is always available because `cycles_waited` is required. |

The caps are the locked hackathon baselines: monthly income `100,000 PKR`, household size `10`, dependents `10`, prior assistance count `5`, school-age children `5`, and cycles waited `6`.

### Missing-value semantics for inverted factors

`income_inverse` and `no_prior_assistance` are inverted scales: lower raw values produce higher priority. This differs from the other factors, where higher raw values produce higher priority.

Locked decision: when `verified_income` or `prior_assistance_count` is missing, its raw-factor score is `0.5`, the neutral midpoint. This prevents missing staff-recorded information from either rewarding or penalizing the candidate; all non-inverted optional factors retain missing-to-`0` behavior.

## 5) Tie-break rule

Sort candidates by this exact sequence:

1. Overall priority score descending.
2. Raw `cycles_waited` descending.
3. Canonical string form of `candidate_id` ascending.

Assign `rank` after this complete sort, starting at `1` and increasing contiguously without gaps. Equal scores must not produce ambiguous ordering or shared rank values.

## 6) Public function design

Create:

- `VerifiedCandidate`: strict Pydantic input model described above.
- `RankedCandidate`: strict Pydantic output model with:
  - `candidate_id: UUID`
  - `overall_priority_score: Decimal`
  - `score_breakdown: dict[str, Decimal]`
  - `rank: positive integer`
- `rank_candidates(candidates, priority_weights) -> list[RankedCandidate]`.

Behavior:

- Performs no I/O.
- Does not mutate candidate inputs or the weights mapping.
- Returns `[]` for an empty candidate sequence.
- For a single valid candidate, returns one complete `RankedCandidate` with rank `1`.
- Rejects invalid weights with `ValueError`.
- Relies on Pydantic validation for invalid candidate field types or invalid negative candidate measurements.

## 7) Test plan

Create standard-library `unittest` tests.

- Negative weight: assert `ValueError`.
- Generic unsupported factor: assert `ValueError`.
- `entry_path` factor: assert `ValueError` specifically.
- Valid normalized weights: assert ranking succeeds.
- Incorrect weight total: assert `ValueError`.
- Single-candidate score: use fixed weights and facts; assert each configured breakdown contribution and assert the Decimal breakdown sum matches `overall_priority_score` within `Decimal("0.000000001")`.
- Missing non-inverted optional factor: omit a weighted non-inverted field such as household size; assert the candidate remains ranked and that factor’s contribution is `0`.
- Missing `verified_income`: use only `income_inverse` with weight `1.0`; assert a missing income produces raw score and contribution `0.5`.
- Missing `prior_assistance_count`: use only `no_prior_assistance` with weight `1.0`; assert a missing count produces raw score and contribution `0.5`.
- Multiple candidates: assert descending overall-score order and ranks `1..n`.
- First tie-break: equal scores with different `cycles_waited`; assert the longer-waiting candidate ranks first.
- Second tie-break: equal scores and equal `cycles_waited`; assert ascending UUID-string order determines ranking.
- Empty candidate list: assert `[]`.
- Single candidate: assert rank `1` and complete breakdown.
- Determinism: call the function twice with identical candidates and weights; assert identical ordered result values.
- Input isolation: rank multiple candidates with distinct facts; assert each breakdown reflects only its own verified values.

## 8) Open questions

None block implementation.

Locked decisions:

- Supplemental vulnerability facts are typed, staff-verified values from `program_specific_data`.
- Missing non-inverted optional facts contribute zero and never remove a verified candidate from ranking.
- Missing values for `income_inverse` and `no_prior_assistance` contribute the neutral midpoint `0.5`.
- Weight totals must equal `1.0` within `0.000001` transport tolerance.
- Scores are normalized to `0–1`.
- Numeric normalization uses the practical fixed caps specified above.
- `entry_path` is actively rejected from priority weights and absent from all candidate/output models.
