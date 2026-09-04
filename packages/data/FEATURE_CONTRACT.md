# Eligibility Feature Contract

This document defines the fixed feature vector used by Task 4.2's XGBoost
confidence model. It is a shared Task 4.2/4.3 contract and contains no
database, API, RAG, or frontend dependency.

## Scope

The model is only called after the hard-rule evaluator returns `pass`. It
estimates whether subsequent staff verification is likely to return
`verified`; it does not decide eligibility or allocation.

## Feature policy

- Nullable numeric and boolean inputs have an explicit paired missingness
  feature. Missing is never converted to zero.
- Categorical fields use a fixed one-hot representation plus a missingness
  feature. Unknown categories are represented as all-zero category flags with
  their missingness flag set only when the source value was absent.
- District is deliberately not a model feature in v1. Location is enforced by
  the hard-rule evaluator; learning arbitrary district effects from a small
  synthetic dataset would be misleading.
- The model has one program-domain indicator for each of the seven scoped
  Al-Khidmat programs: Disaster Management, Health Services, Education
  Program, WASH Program, Orphan Care Program, Bano Qabil Program, and Islamic
  Microfinance.
- `avg_numeric_rule_slack` is the only program-criterion feature. It captures
  how far a rule-passing profile is from its numeric limits without creating a
  variable-width feature vector.

## Synthetic labels

Synthetic labels combine low income per household member, dependent pressure,
disability/chronic-illness interaction, orphan status, prior assistance, a
small program effect, random variation, and a 10% label flip. They are not a
claim about real Al-Khidmat decisions.

The train/test split is grouped by beneficiary profile. A profile can have
multiple program matches, but none of those matches may appear in both splits.
That prevents the model from being evaluated on a profile it has effectively
already seen.
