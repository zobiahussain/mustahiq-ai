"""Discovery-orchestration tests required by PLAN_reasoning_discovery.md."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

PACKAGES_DIR = Path(__file__).resolve().parents[2]
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from data.synthetic import SyntheticProgram, build_synthetic_programs

from eligibility.discovery import SUPPRESSION_SUFFIX, DiscoveryProgram, discover_profile
from eligibility.models import BeneficiaryProfile


PROGRAMS = {program.id: program for program in build_synthetic_programs()}
WASH = PROGRAMS["wash-program-demo"]
EDUCATION = PROGRAMS["education-program-demo"]
HEALTH = PROGRAMS["health-services-demo"]
BANO_QABIL = PROGRAMS["bano-qabil-demo"]


class RecordingScorer:
    """Test double honouring the SavedScorer.predict_confidence contract."""

    def __init__(self, score: float = 0.7) -> None:
        self.score = score
        self.calls = 0

    def predict_confidence(self, feature_row: dict) -> float:
        self.calls += 1
        return self.score


def discovery_program(
    program: SyntheticProgram,
    *,
    requires_explicit_application: bool = False,
) -> DiscoveryProgram:
    return DiscoveryProgram(
        program_id=program.id,
        name=program.name,
        domain=program.domain,  # type: ignore[arg-type]
        rules=list(program.rules),
        requires_explicit_application=requires_explicit_application,
    )


def _explicit_application_pass_profile() -> BeneficiaryProfile:
    """A profile that clears an ordinary programme's rules -- used to prove the
    ``requires_explicit_application`` suppression path, which is a generic
    mechanism (any programme an admin flags), not tied to one programme.
    """
    return BeneficiaryProfile(
        date_of_birth=date.today() - timedelta(days=30 * 365),
        employment_status="unemployed",
    )


class DiscoveryTests(unittest.TestCase):
    def test_wash_failure_is_not_eligible_without_scorer_call(self) -> None:
        profile = BeneficiaryProfile(district="Lahore")
        scorer = RecordingScorer()

        results = discover_profile(profile, [discovery_program(WASH)], scorer)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "not_eligible")
        self.assertIsNone(results[0].score)
        self.assertIn("Water-stressed district", results[0].reason)
        self.assertEqual(scorer.calls, 0)

    def test_education_incomplete_requests_missing_information(self) -> None:
        profile = BeneficiaryProfile()
        scorer = RecordingScorer()

        results = discover_profile(profile, [discovery_program(EDUCATION)], scorer)

        self.assertEqual(results[0].status, "incomplete")
        self.assertIsNone(results[0].score)
        self.assertTrue(results[0].reason.startswith("More information is needed"))
        self.assertEqual(scorer.calls, 0)

    def test_bano_qabil_pass_is_pending_review_with_score(self) -> None:
        profile = BeneficiaryProfile(employment_status="unemployed")
        scorer = RecordingScorer(0.70)

        results = discover_profile(profile, [discovery_program(BANO_QABIL)], scorer)

        self.assertEqual(results[0].status, "pending_review")
        self.assertEqual(results[0].score, 0.70)
        self.assertIn("Verification confidence: high", results[0].reason)
        self.assertEqual(scorer.calls, 1)

    def test_explicit_application_pass_is_suppressed_with_suffix(self) -> None:
        profile = _explicit_application_pass_profile()
        scorer = RecordingScorer(0.7)

        results = discover_profile(
            profile,
            [discovery_program(BANO_QABIL, requires_explicit_application=True)],
            scorer,
        )

        self.assertEqual(results[0].status, "suppressed")
        self.assertEqual(results[0].score, 0.7)
        self.assertEqual(scorer.calls, 1)
        self.assertTrue(results[0].reason.endswith(SUPPRESSION_SUFFIX))

    def test_one_profile_across_three_programmes_preserves_order(self) -> None:
        profile = BeneficiaryProfile(
            monthly_income=Decimal("25000"),
            school_age_children=2,
            district="Lahore",
            chronic_illness_flag=None,
        )
        scorer = RecordingScorer(0.7)

        results = discover_profile(
            profile,
            [discovery_program(EDUCATION), discovery_program(WASH), discovery_program(HEALTH)],
            scorer,
        )

        self.assertEqual(
            [result.status for result in results],
            ["pending_review", "not_eligible", "incomplete"],
        )
        self.assertEqual([result.program_id for result in results], [EDUCATION.id, WASH.id, HEALTH.id])
        scored = [result.score for result in results]
        self.assertIsNotNone(scored[0])
        self.assertIsNone(scored[1])
        self.assertIsNone(scored[2])
        self.assertEqual(scorer.calls, 1)

    def test_repeated_calls_with_separate_scorers_are_isolated(self) -> None:
        profile = BeneficiaryProfile(employment_status="unemployed")
        programs = [discovery_program(BANO_QABIL)]

        first_scorer = RecordingScorer(0.7)
        second_scorer = RecordingScorer(0.7)

        first_results = discover_profile(profile, programs, first_scorer)
        second_results = discover_profile(profile, programs, second_scorer)

        self.assertEqual(first_results, second_results)
        self.assertEqual(first_scorer.calls, 1)
        self.assertEqual(second_scorer.calls, 1)


if __name__ == "__main__":
    unittest.main()
