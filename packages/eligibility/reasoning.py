"""Deterministic staff-facing explanations for eligibility rule outcomes."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .models import ProgramRule, RuleEvaluationResult


MISSING_FIELD_LABELS = {
    "monthly_income": "monthly income",
    "household_size": "household size",
    "dependents": "number of dependents",
    "school_age_children": "number of school-age children",
    "marital_status": "marital status",
    "employment_status": "employment status",
    "owns_home": "home ownership",
    "district": "district",
    "city": "city",
    "education_level": "education level",
    "has_disability": "disability status",
    "chronic_illness_flag": "chronic illness status",
    "prior_assistance_count": "prior assistance count",
    "age": "date of birth",
    "is_orphan": "orphan status",
}


def _join_items(items: Sequence[str]) -> str:
    if not items:
        raise ValueError("at least one item is required")
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _confidence_band(confidence_score: float | None) -> str:
    if confidence_score is None:
        raise ValueError("pass results require a confidence score")
    if isinstance(confidence_score, bool) or not isinstance(confidence_score, (int, float)):
        raise ValueError("confidence score must be a finite number")
    if not math.isfinite(confidence_score) or not 0.0 <= confidence_score <= 1.0:
        raise ValueError("confidence score must be between 0.0 and 1.0")
    if confidence_score < 0.40:
        return "low"
    if confidence_score < 0.70:
        return "medium"
    return "high"


def _descriptions_for_rule_ids(
    rule_ids: Sequence[str],
    rules: Sequence[ProgramRule],
) -> list[str]:
    descriptions_by_id = {rule.rule_id: rule.description for rule in rules}
    descriptions: list[str] = []
    for rule_id in rule_ids:
        if rule_id not in descriptions_by_id:
            raise ValueError(f"rule ID '{rule_id}' was not supplied")
        descriptions.append(descriptions_by_id[rule_id])
    return descriptions


def explain(
    evaluation: RuleEvaluationResult,
    rules: Sequence[ProgramRule],
    confidence_score: float | None,
) -> str:
    """Return one deterministic, staff-readable explanation for a rule outcome."""

    if evaluation.status == "fail":
        if confidence_score is not None:
            raise ValueError("fail results must not include a confidence score")
        descriptions = _descriptions_for_rule_ids(evaluation.failed_rules, rules)
        return (
            "Not eligible for this programme based on the current information "
            f"because it does not meet: {_join_items(descriptions)}."
        )

    if evaluation.status == "incomplete":
        if confidence_score is not None:
            raise ValueError("incomplete results must not include a confidence score")
        labels: list[str] = []
        for field_name in evaluation.missing_fields:
            if field_name not in MISSING_FIELD_LABELS:
                raise ValueError(f"missing field '{field_name}' has no display label")
            labels.append(MISSING_FIELD_LABELS[field_name])
        return f"More information is needed to assess this programme: {_join_items(labels)}."

    descriptions = _descriptions_for_rule_ids(evaluation.passed_rules, rules)
    return (
        f"Suggested because it meets: {_join_items(descriptions)}. "
        f"Verification confidence: {_confidence_band(confidence_score)}."
    )
