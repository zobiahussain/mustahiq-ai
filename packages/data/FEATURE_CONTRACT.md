# Eligibility Model Feature Contract and Target Label

This is the reference for the Task 4.2 XGBoost confidence model. It defines
every input feature (`X`) and the training target (`y`). The implementation is
in [features.py](features.py); synthetic demo labels are in
[synthetic.py](synthetic.py).

## What the model predicts

The model answers one question only: for a beneficiary who already passed a
programme's hard rules, how likely is staff verification to confirm the match?
It does not decide eligibility, create an application, or rank funding.

```text
Profile + programme rules -> hard-rule evaluator
fail / incomplete         -> do not call the model
pass                      -> features (X) -> XGBoost -> confidence: 0.0 to 1.0
```

The vector has **57 fixed float64 features**. Their order is saved alongside
every trained model artifact.

## Missing-data policy

Missing numeric and Boolean values are never replaced with zero. A missing
value becomes `NaN`, while its paired `<feature>_missing` flag becomes `1.0`.
A genuine `0` or `false` remains a known value with missing flag `0.0`.

| Input situation   | `monthly_income` | `monthly_income_missing` |
| ----------------- | ---------------: | -----------------------: |
| Income unknown    |            `NaN` |                    `1.0` |
| Income PKR 0      |            `0.0` |                    `0.0` |
| Income PKR 25,000 |        `25000.0` |                    `0.0` |

## Feature dictionary (`X`)

### Raw numeric profile values — 12 features

Each source field creates its value and a missingness flag.

| Source field                     | Features                                                   | Purpose                                                            |
| -------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------ |
| `monthly_income`                 | `monthly_income`, `monthly_income_missing`                 | Economic context.                                                  |
| `household_size`                 | `household_size`, `household_size_missing`                 | Household demand.                                                  |
| `dependents`                     | `dependents`, `dependents_missing`                         | Household burden.                                                  |
| `school_age_children`            | `school_age_children`, `school_age_children_missing`       | Household and education context.                                   |
| `prior_assistance_count`         | `prior_assistance_count`, `prior_assistance_count_missing` | Previous support context; never automatic exclusion.               |
| Derived age from `date_of_birth` | `age`, `age_missing`                                       | Child, youth, and working-age context without storing a stale age. |

### Derived household and policy-fit signals — 14 features

| Feature                       | Paired flag                           | Calculation                                                       | Purpose                                                                |
| ----------------------------- | ------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `income_per_head`             | `income_per_head_missing`             | `monthly_income / household_size`                                 | Compares income fairly across household sizes.                         |
| `dependents_to_earners_ratio` | `dependents_to_earners_ratio_missing` | `dependents / max(household_size - dependents, 1)`                | Demo proxy for dependency pressure, not a literal earner count.        |
| `dependency_share`            | `dependency_share_missing`            | `dependents / household_size`                                     | Fraction of the household that cannot self-support; a depth-3 tree cannot synthesise this from the two raw columns. |
| `school_age_ratio`            | `school_age_ratio_missing`            | `school_age_children / household_size`                            | Education-cost pressure relative to household size.                    |
| `vulnerability_count`         | `vulnerability_count_missing`         | Count of confirmed markers among `has_disability`, `chronic_illness_flag`, `is_orphan` | Compound vulnerability in one number; missing only when all three markers are unknown. |
| `is_sole_earner`              | `is_sole_earner_missing`              | `1.0` if `household_size - dependents <= 1`                       | Single-earner household flag.                                         |
| `avg_numeric_rule_slack`      | `avg_numeric_rule_slack_missing`      | Average normalized distance from `<=` / `>=` programme thresholds | Strength of fit inside the policy boundary, never an allocation score. |

### Boolean vulnerability and housing signals — 8 features

Known Booleans become `1.0` for true and `0.0` for false, with a paired flag.

| Source field           | Features                                               | Purpose                                        |
| ---------------------- | ------------------------------------------------------ | ---------------------------------------------- |
| `has_disability`       | `has_disability`, `has_disability_missing`             | Vulnerability context.                         |
| `chronic_illness_flag` | `chronic_illness_flag`, `chronic_illness_flag_missing` | Health vulnerability context.                  |
| `is_orphan`            | `is_orphan`, `is_orphan_missing`                       | Orphan Care and general vulnerability context. |
| `owns_home`            | `owns_home`, `owns_home_missing`                       | Household stability context.                   |

### Education-level indicators — 6 features

- `education_level_none`
- `education_level_primary`
- `education_level_matric`
- `education_level_intermediate`
- `education_level_graduate`
- `education_level_missing`

### Employment-status indicators — 5 features

- `employment_status_unemployed`
- `employment_status_daily_wage`
- `employment_status_self_employed`
- `employment_status_salaried`
- `employment_status_missing`

### Marital-status indicators — 5 features

- `marital_status_single`
- `marital_status_married`
- `marital_status_widowed`
- `marital_status_divorced`
- `marital_status_missing`

### Programme-domain indicators — 7 features

Exactly one indicator is `1.0` for each profile/programme pair.

- `program_domain_disaster_management`
- `program_domain_health_services`
- `program_domain_education`
- `program_domain_wash`
- `program_domain_orphan_care`
- `program_domain_bano_qabil`
- `program_domain_community_services`

The seven values are Al-Khidmat's real areas of work
(alkhidmat.org/donations/area-of-work). Islamic Microfinance is **not** a
domain here: a loan is not something a beneficiary is "eligible" for without
applying, so it is handled only in the marketplace module. Programme
sub-programmes (for example Thalassemia Care and Dialysis under Health) share
their parent's domain indicator; the model separates them through the profile
features and `avg_numeric_rule_slack`, not a dedicated column.

## Fields deliberately excluded

| Excluded field                    | Reason                                                                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Name, CNIC, phone                 | Identity/contact data is not an eligibility-confidence signal.                                                            |
| `staff_notes`                     | Human context only, not a model input.                                                                                    |
| `entry_path`                      | Direct and AI-identified candidates must never be treated differently.                                                    |
| Discovery confidence / need score | Prevents circular logic and keeps discovery separate from allocation.                                                     |
| `district`, `city`, `cluster_id`  | Location belongs in explicit, auditable hard rules; synthetic data is too small to learn trustworthy geographic patterns. |
| RAG output / free text            | Retrieval never runs in deterministic eligibility scoring.                                                                |

## Training target (`y` label)

The target field is `verified`.

| `verified` | Numeric `y` | Meaning                                 |
| ---------: | ----------: | --------------------------------------- |
|    `False` |         `0` | Verification was not confirmed.         |
|     `True` |         `1` | Staff verification confirmed the match. |

For the hackathon, `y` is synthetic only. A row is created only when that
profile/programme pair has a hard-rule `pass` result:

```text
hard-rule fail or incomplete -> no training row
hard-rule pass               -> features (X) + verified label (y)
```

The synthetic label probability combines lower income per household member,
higher dependency pressure, disability/chronic-illness interaction, orphan and
widow status, insecure housing, informal or absent employment, low education,
school-age children, prior assistance, a per-domain programme effect, random
Gaussian variation, and a final label flip (`noise_rate`, 0.08). Profiles are
drawn from a single latent "hardship" factor so the columns move together the
way a real caseload does. It demonstrates an end-to-end ML pipeline; it does
not prove real-world accuracy.

### How much data the demo model trains on

`run_model_pipeline.py` defaults to **15,000 synthetic profiles** (an earlier
revision used 3,000). Each profile is evaluated against all 22 sub-programmes;
every hard-rule `pass` becomes one labelled `(profile, programme)` row, so the
15,000 profiles yield roughly 40,000–55,000 training rows. The split is an
80/20 `StratifiedGroupKFold` grouped by profile, so no beneficiary appears in
both train and test. The exact counts and held-out precision/recall/F1/ROC-AUC
for the shipped artifact are written to
`artifacts/eligibility-scorer/scorer_metadata.json` at train time.

## Future target and guardrails

If the team explicitly approves real verification data for future training,
the intended mapping is `verifications.outcome == "verified"` to `y = 1`; all
other final outcomes map to `y = 0`. Do not implement automatic retraining yet:
the project documents have an unresolved beneficiary-data governance conflict.

- Invoke XGBoost only after hard-rule `pass`.
- A confidence score is a staff suggestion, never a decision or funding rank.
- `entry_path` and XGBoost confidence must never enter the prioritisation rubric.
- The saved artifact must have the same feature-column contract as this file.
