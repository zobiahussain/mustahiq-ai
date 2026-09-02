"""Public interface for deterministic eligibility rule evaluation."""

from .evaluator import evaluate_rules
from .models import BeneficiaryProfile, ProgramRule, RuleEvaluationResult

__all__ = [
    "BeneficiaryProfile",
    "ProgramRule",
    "RuleEvaluationResult",
    "evaluate_rules",
]
