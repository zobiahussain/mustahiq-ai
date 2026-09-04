"""Build a stable numeric feature vector for eligibility confidence scoring."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import pandas as pd

from eligibility.models import BeneficiaryProfile, NUMERIC_FIELDS, ProgramRule


PROGRAM_DOMAINS = (
    "disaster_management",
    "health_services",
    "education",
    "wash",
    "orphan_care",
    "bano_qabil",
    "islamic_microfinance",
)
EDUCATION_LEVELS = ("none", "primary", "matric", "intermediate", "graduate")
EMPLOYMENT_STATUSES = ("unemployed", "daily_wage", "self_employed", "salaried")
MARITAL_STATUSES = ("single", "married", "widowed", "divorced")

NUMERIC_PROFILE_FIELDS = (
    "monthly_income",
    "household_size",
    "dependents",
    "school_age_children",
    "prior_assistance_count",
    "age",
)
BOOLEAN_PROFILE_FIELDS = (
    "has_disability",
    "chronic_illness_flag",
    "is_orphan",
    "owns_home",
)

FEATURE_COLUMNS = (
    *(column for name in NUMERIC_PROFILE_FIELDS for column in (name, f"{name}_missing")),
    "income_per_head",
    "income_per_head_missing",
    "dependents_to_earners_ratio",
    "dependents_to_earners_ratio_missing",
    "avg_numeric_rule_slack",
    "avg_numeric_rule_slack_missing",
    *(column for name in BOOLEAN_PROFILE_FIELDS for column in (name, f"{name}_missing")),
    *(f"education_level_{level}" for level in EDUCATION_LEVELS),
    "education_level_missing",
    *(f"employment_status_{status}" for status in EMPLOYMENT_STATUSES),
    "employment_status_missing",
    *(f"marital_status_{status}" for status in MARITAL_STATUSES),
    "marital_status_missing",
    *(f"program_domain_{domain}" for domain in PROGRAM_DOMAINS),
)


def _numeric_with_missing(value: int | Decimal | None) -> tuple[float, float]:
    if value is None:
        return float("nan"), 1.0
    return float(value), 0.0


def _boolean_with_missing(value: bool | None) -> tuple[float, float]:
    if value is None:
        return float("nan"), 1.0
    return float(value), 0.0


def _add_one_hot(
    row: dict[str, float],
    *,
    prefix: str,
    value: str | None,
    allowed_values: Sequence[str],
) -> None:
    for allowed_value in allowed_values:
        row[f"{prefix}_{allowed_value}"] = float(value == allowed_value)
    row[f"{prefix}_missing"] = float(value is None)


def _average_numeric_rule_slack(
    profile: BeneficiaryProfile,
    rules: Sequence[ProgramRule],
) -> tuple[float, float]:
    slacks: list[float] = []
    for rule in rules:
        if rule.field not in NUMERIC_FIELDS or rule.operator not in {"<=", ">="}:
            continue
        profile_value = getattr(profile, rule.field)
        if profile_value is None:
            continue

        threshold = float(rule.value)
        if threshold == 0:
            continue
        if rule.operator == "<=":
            slacks.append((threshold - float(profile_value)) / threshold)
        else:
            slacks.append((float(profile_value) - threshold) / threshold)

    if not slacks:
        return float("nan"), 1.0
    return sum(slacks) / len(slacks), 0.0


def build_feature_row(
    profile: BeneficiaryProfile,
    *,
    program_domain: str,
    program_rules: Sequence[ProgramRule],
) -> dict[str, float]:
    """Build one fixed-width, all-numeric row for XGBoost.

    The hard-rule evaluator owns eligibility. This function assumes the
    profile/program pair already passed that gate and only represents soft
    confidence signals.
    """

    if program_domain not in PROGRAM_DOMAINS:
        raise ValueError(f"Unsupported program domain: {program_domain}")

    row: dict[str, float] = {}
    for name in NUMERIC_PROFILE_FIELDS:
        value, missing = _numeric_with_missing(getattr(profile, name))
        row[name] = value
        row[f"{name}_missing"] = missing

    if profile.monthly_income is None or profile.household_size in {None, 0}:
        row["income_per_head"] = float("nan")
        row["income_per_head_missing"] = 1.0
    else:
        row["income_per_head"] = float(profile.monthly_income) / profile.household_size
        row["income_per_head_missing"] = 0.0

    if profile.household_size in {None, 0} or profile.dependents is None:
        row["dependents_to_earners_ratio"] = float("nan")
        row["dependents_to_earners_ratio_missing"] = 1.0
    else:
        earners = max(profile.household_size - profile.dependents, 1)
        row["dependents_to_earners_ratio"] = profile.dependents / earners
        row["dependents_to_earners_ratio_missing"] = 0.0

    slack, slack_missing = _average_numeric_rule_slack(profile, program_rules)
    row["avg_numeric_rule_slack"] = slack
    row["avg_numeric_rule_slack_missing"] = slack_missing

    for name in BOOLEAN_PROFILE_FIELDS:
        value, missing = _boolean_with_missing(getattr(profile, name))
        row[name] = value
        row[f"{name}_missing"] = missing

    _add_one_hot(
        row,
        prefix="education_level",
        value=profile.education_level,
        allowed_values=EDUCATION_LEVELS,
    )
    _add_one_hot(
        row,
        prefix="employment_status",
        value=profile.employment_status,
        allowed_values=EMPLOYMENT_STATUSES,
    )
    _add_one_hot(
        row,
        prefix="marital_status",
        value=profile.marital_status,
        allowed_values=MARITAL_STATUSES,
    )
    for domain in PROGRAM_DOMAINS:
        row[f"program_domain_{domain}"] = float(program_domain == domain)

    return row


def build_feature_frame(rows: Sequence[dict[str, Any]]) -> pd.DataFrame:
    """Return the contract columns in a stable order for train and predict."""

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS, dtype="float64")
