# Reasoning and Discovery Implementation Plan

This file is the source of truth for the Task 4.2 `reasoning.py` and
`discovery.py` modules. They are pure Python eligibility-engine components:
they do not read or write Supabase, call FastAPI, use RAG, train models, or
create workflow jobs.

## 1. Scope and non-goals

`reasoning.py` turns a completed hard-rule evaluation into deterministic
plain-language text. `discovery.py` evaluates one profile against many active
programmes, calls the saved scorer only for rule passes, and returns one
in-memory result per programme.

Deferred work: database persistence, API integration, workflow triggers,
programme loading/filtering, model training, feature-engineering changes,
prioritization, staff pooling, and all RAG behavior. The caller supplies only
active programmes. `discovery.py` does not query the database.

## 2. `reasoning.py` design

### Public interface

The `explain` function receives a `RuleEvaluationResult`, the ordered rules
used for that evaluation, and a confidence score that is a float or `None`.
It returns one non-empty deterministic reason string.

For `pass`, confidence is required, finite, and in the inclusive range 0.0 to
1.0. For `fail` and `incomplete`, confidence must be `None`. Violations raise
`ValueError`. Every passed or failed rule ID must resolve to a supplied rule;
an unresolved ID raises `ValueError`.

### Formatting rules

Preserve the evaluator's input/result ordering; do not sort rules or missing
fields. Join items as: one item `A`; two items `A and B`; three or more
`A, B, and C`.

Use these exact labels for missing fields:

| Field | Label |
|---|---|
| `monthly_income` | monthly income |
| `household_size` | household size |
| `dependents` | number of dependents |
| `school_age_children` | number of school-age children |
| `marital_status` | marital status |
| `employment_status` | employment status |
| `owns_home` | home ownership |
| `district` | district |
| `city` | city |
| `education_level` | education level |
| `has_disability` | disability status |
| `chronic_illness_flag` | chronic illness status |
| `prior_assistance_count` | prior assistance count |
| `age` | date of birth |
| `is_orphan` | orphan status |

Use these exact templates:

| Evaluation | Template |
|---|---|
| `fail` | `Not eligible for this programme based on the current information because it does not meet: {failed rule descriptions}.` |
| `incomplete` | `More information is needed to assess this programme: {human-readable missing fields}.` |
| `pass` | `Suggested because it meets: {passed rule descriptions}. Verification confidence: {confidence band}.` |

Rule text comes from `ProgramRule.description`, never a rule ID. A pass with
no passed rules is invalid and raises `ValueError`.

Confidence bands are fixed:

| Score | Label |
|---|---|
| 0.00 to below 0.40 | low |
| 0.40 to below 0.70 | medium |
| 0.70 through 1.00 | high |

Raw confidence floats never appear in the text.

## 3. `discovery.py` design

### Public models

`DiscoveryProgram` is a strict Pydantic model with non-empty `program_id` and
`name`; locally declared domain literal; non-empty ordered rules; and
`requires_explicit_application`, defaulting to false.

The local domain literal contains exactly:

```text
disaster_management, health_services, education, wash, orphan_care,
bano_qabil, islamic_microfinance
```

Do not import a domain constant from `data.features` or edit that module.

`DiscoveryResult` is a strict Pydantic model with non-empty `program_id` and
`reason`, a status, and a score. Its allowed statuses are:

| Hard-rule result | Explicit application | Result status | Score |
|---|---:|---|---|
| pass | false | `pending_review` | confidence float |
| pass | true | `suppressed` | confidence float |
| fail | either | `not_eligible` | `None` |
| incomplete | either | `incomplete` | `None` |

Only `pending_review` and `suppressed` map to future `match_records` rows.
`not_eligible` and `incomplete` remain in-memory outcomes by default.

### Public interface and control flow

`discover_profile` receives one `BeneficiaryProfile`, an ordered sequence of
`DiscoveryProgram`, and one already-loaded `SavedScorer`. It returns an ordered
list containing one `DiscoveryResult` for every supplied programme.

One profile plus many programmes is the correct unit: a registration/profile
update must check the profile against all active programmes. Bulk re-scans loop
profiles outside this function.

```text
For each programme in supplied order:
  evaluate hard rules
    fail       -> explanation without score -> not_eligible
    incomplete -> explanation without score -> incomplete
    pass       -> build existing feature row
               -> scorer.predict_confidence
               -> pass explanation
               -> pending_review, or suppressed if explicit application is required
```

For an explicit-application pass, append exactly this suffix to the pass
explanation:

```text
 This programme requires an explicit application and will not be sent for proactive outreach.
```

Feature construction and scorer inference must never run for `fail` or
`incomplete`. Results preserve input order and have no shared mutable state.
The caller loads the scorer; discovery performs no artifact I/O.

## 4. Test plan

Tests use `unittest`. Where practical, use `build_synthetic_programs()` and
`generate_synthetic_profiles()`, then `model_copy(update=...)` only to force a
known condition. Discovery unit tests use a recording scorer test double, not
XGBoost training or artifact loading.

### `reasoning.py`

- One Education Program income failure: exact text contains `Income threshold`, does not contain `EDU-01`, and follows the failure template.
- Multiple Health Services failures: exact reason contains income then chronic-illness descriptions in programme order joined by `and`.
- One missing Education Program input: exact text requests `monthly income` and does not call the case a rejection.
- Multiple missing Education Program inputs: exact text includes `monthly income and number of school-age children`.
- Confidence boundaries: scores 0.00 and 0.3999 say low; 0.40 and 0.6999 say medium; 0.70 and 1.00 say high.
- Determinism: identical pass inputs return exactly equal strings twice.
- Validation: pass without a score; fail with score; score below 0; score above 1; NaN; and infinity each raise `ValueError`.

### `discovery.py`

- WASH failure: output is `not_eligible`, score is `None`, reason uses `Water-stressed district`, and scorer call count is zero.
- Education incomplete: output is `incomplete`, score is `None`, reason requests missing information, and scorer call count is zero.
- Bano Qabil pass: output is `pending_review`, score equals recorded scorer output, high-band text is present for 0.70, and scorer call count is one.
- Explicit-application programme pass (any programme flagged `requires_explicit_application`): output is `suppressed`, retains its score, calls scorer once, and ends with the exact suppression suffix. (The flag existed for Islamic Microfinance, which is no longer an eligibility-side programme; the mechanism is generic.)
- One profile against Education, WASH, and Health: returns three results in input order with `pending_review`, `not_eligible`, and `incomplete`; only the first has a score; scorer call count is one.
- Repeated calls with separate recording scorers: result values are equal and each scorer records only its own expected call.

## 5. Open questions

None block implementation.

Locked assumptions: actionable discovery statuses are `pending_review`,
`suppressed`, `not_eligible`, and `incomplete`; explanation confidence bands
are low below 0.40, medium below 0.70, and high otherwise; and only actionable
statuses are persisted later.
