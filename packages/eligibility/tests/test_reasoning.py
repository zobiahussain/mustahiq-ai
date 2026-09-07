"""Deterministic-explanation tests required by PLAN_reasoning_discovery.md."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

PACKAGES_DIR = Path(__file__).resolve().parents[2]
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from data.synthetic import build_synthetic_programs

from eligibility.evaluator import evaluate_rules
from eligibility.models import BeneficiaryProfile
from eligibility.reasoning import explain


PROGRAMS = {program.id: program for program in build_synthetic_programs()}
EDUCATION = PROGRAMS["education-program-demo"]
HEALTH = PROGRAMS["health-services-demo"]
BANO_QABIL = PROGRAMS["bano-qabil-demo"]


def _education_failure_profile() -> BeneficiaryProfile:
    return BeneficiaryProfile(monthly_income=Decimal("50000"), school_age_children=2)


def _health_multi_failure_profile() -> BeneficiaryProfile:
    return BeneficiaryProfile(monthly_income=Decimal("50000"), chronic_illness_flag=False)


def _education_missing_income_profile() -> BeneficiaryProfile:
    return BeneficiaryProfile(school_age_children=2)


def _education_missing_both_profile() -> BeneficiaryProfile:
    return BeneficiaryProfile()


def _bano_qabil_pass_profile() -> BeneficiaryProfile:
    return BeneficiaryProfile(employment_status="unemployed")


class ReasoningTests(unittest.TestCase):
    def test_single_education_failure_uses_description_not_rule_id(self) -> None:
        evaluation = evaluate_rules(_education_failure_profile(), EDUCATION.rules)

        self.assertEqual(evaluation.status, "fail")
        reason = explain(evaluation, EDUCATION.rules, None)

        self.assertIn("Income threshold", reason)
        self.assertNotIn("EDU-01", reason)
        self.assertEqual(
            reason,
            "Not eligible for this programme based on the current information "
            "because it does not meet: Income threshold.",
        )

    def test_multiple_health_failures_join_in_programme_order(self) -> None:
        evaluation = evaluate_rules(_health_multi_failure_profile(), HEALTH.rules)

        self.assertEqual(evaluation.status, "fail")
        reason = explain(evaluation, HEALTH.rules, None)

        self.assertEqual(
            reason,
            "Not eligible for this programme based on the current information "
            "because it does not meet: Income threshold and Chronic illness confirmed.",
        )

    def test_one_missing_education_input_requests_information(self) -> None:
        evaluation = evaluate_rules(_education_missing_income_profile(), EDUCATION.rules)

        self.assertEqual(evaluation.status, "incomplete")
        reason = explain(evaluation, EDUCATION.rules, None)

        self.assertIn("monthly income", reason)
        self.assertNotIn("Not eligible", reason)
        self.assertEqual(
            reason,
            "More information is needed to assess this programme: monthly income.",
        )

    def test_multiple_missing_education_inputs_are_joined(self) -> None:
        evaluation = evaluate_rules(_education_missing_both_profile(), EDUCATION.rules)

        self.assertEqual(evaluation.status, "incomplete")
        reason = explain(evaluation, EDUCATION.rules, None)

        self.assertEqual(
            reason,
            "More information is needed to assess this programme: "
            "monthly income and number of school-age children.",
        )

    def test_confidence_boundaries(self) -> None:
        evaluation = evaluate_rules(_bano_qabil_pass_profile(), BANO_QABIL.rules)
        self.assertEqual(evaluation.status, "pass")

        expected_bands = [
            (0.00, "low"),
            (0.3999, "low"),
            (0.40, "medium"),
            (0.6999, "medium"),
            (0.70, "high"),
            (1.00, "high"),
        ]
        for score, band in expected_bands:
            with self.subTest(score=score):
                reason = explain(evaluation, BANO_QABIL.rules, score)
                self.assertIn(f"Verification confidence: {band}.", reason)

    def test_identical_pass_inputs_produce_identical_text(self) -> None:
        evaluation = evaluate_rules(_bano_qabil_pass_profile(), BANO_QABIL.rules)

        first = explain(evaluation, BANO_QABIL.rules, 0.72)
        second = explain(evaluation, BANO_QABIL.rules, 0.72)
        self.assertEqual(first, second)

    def test_pass_without_confidence_score_is_rejected(self) -> None:
        evaluation = evaluate_rules(_bano_qabil_pass_profile(), BANO_QABIL.rules)

        with self.assertRaises(ValueError):
            explain(evaluation, BANO_QABIL.rules, None)

    def test_fail_with_confidence_score_is_rejected(self) -> None:
        evaluation = evaluate_rules(_education_failure_profile(), EDUCATION.rules)

        with self.assertRaises(ValueError):
            explain(evaluation, EDUCATION.rules, 0.5)

    def test_out_of_range_and_non_finite_scores_are_rejected(self) -> None:
        evaluation = evaluate_rules(_bano_qabil_pass_profile(), BANO_QABIL.rules)

        for score in (-0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(score=score), self.assertRaises(ValueError):
                explain(evaluation, BANO_QABIL.rules, score)


if __name__ == "__main__":
    unittest.main()
