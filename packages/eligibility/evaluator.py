"""Deterministic, side-effect-free hard-rule evaluation."""

from collections.abc import Callable, Sequence
from decimal import Decimal

from .models import BeneficiaryProfile, ProgramRule, RuleEvaluationResult


def _normalise_text(value: str) -> str:
    return value.strip().casefold()


def _as_decimal(value: int | Decimal) -> Decimal:
    if isinstance(value, bool):
        raise TypeError("Boolean values cannot be compared as numbers")
    return Decimal(value)


def _less_than_or_equal(profile_value: object, rule_value: object) -> bool:
    return _as_decimal(profile_value) <= _as_decimal(rule_value)  # type: ignore[arg-type]


def _greater_than_or_equal(profile_value: object, rule_value: object) -> bool:
    return _as_decimal(profile_value) >= _as_decimal(rule_value)  # type: ignore[arg-type]


def _equals(profile_value: object, rule_value: object) -> bool:
    if isinstance(profile_value, str) and isinstance(rule_value, str):
        return _normalise_text(profile_value) == _normalise_text(rule_value)
    return profile_value == rule_value


def _is_in(profile_value: object, rule_value: object) -> bool:
    if not isinstance(profile_value, str) or not isinstance(rule_value, list):
        raise TypeError("in comparisons require a string profile value and a list rule value")
    normalised_options = {_normalise_text(option) for option in rule_value}
    return _normalise_text(profile_value) in normalised_options


OPERATOR_HANDLERS: dict[str, Callable[[object, object], bool]] = {
    "<=": _less_than_or_equal,
    ">=": _greater_than_or_equal,
    "==": _equals,
    "in": _is_in,
}


def evaluate_rules(
    profile: BeneficiaryProfile,
    rules: Sequence[ProgramRule],
) -> RuleEvaluationResult:
    """Evaluate confirmed program rules against one partial beneficiary profile.

    A failed rule takes precedence over missing information. Missing values are reported
    only when the available information has not already established a hard failure.
    """

    passed_rules: list[str] = []
    failed_rules: list[str] = []
    missing_fields: list[str] = []

    for rule in rules:
        profile_value = getattr(profile, rule.field)
        if profile_value is None:
            if rule.field not in missing_fields:
                missing_fields.append(rule.field)
            continue

        handler = OPERATOR_HANDLERS[rule.operator]
        if handler(profile_value, rule.value):
            passed_rules.append(rule.rule_id)
        else:
            failed_rules.append(rule.rule_id)

    if failed_rules:
        status = "fail"
    elif missing_fields:
        status = "incomplete"
    else:
        status = "pass"

    return RuleEvaluationResult(
        status=status,
        passed_rules=passed_rules,
        failed_rules=failed_rules,
        missing_fields=missing_fields,
    )
