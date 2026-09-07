"""Prioritization-rubric tests required by PLAN_prioritization.md."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from uuid import UUID

from pathlib import Path

PACKAGES_DIR = Path(__file__).resolve().parents[2]
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from eligibility.prioritization import VerifiedCandidate, rank_candidates


CANDIDATE_A_ID = UUID("00000000-0000-0000-0000-000000000001")
CANDIDATE_B_ID = UUID("00000000-0000-0000-0000-000000000002")
CANDIDATE_C_ID = UUID("00000000-0000-0000-0000-000000000003")


def candidate(**overrides: object) -> VerifiedCandidate:
    values: dict[str, object] = {
        "candidate_id": CANDIDATE_A_ID,
        "cycles_waited": 0,
    }
    values.update(overrides)
    return VerifiedCandidate(**values)


class WeightValidationTests(unittest.TestCase):
    def test_negative_weight_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            rank_candidates([], {"urgency": -0.5, "dependents": 1.5})

    def test_unsupported_factor_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            rank_candidates([], {"urgency": 0.5, "favourite_colour": 0.5})

    def test_entry_path_factor_is_rejected_specifically(self) -> None:
        with self.assertRaisesRegex(ValueError, "entry_path"):
            rank_candidates([], {"entry_path": 0.5, "urgency": 0.5})

    def test_boolean_weight_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            rank_candidates([], {"urgency": True})

    def test_non_numeric_weight_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            rank_candidates([], {"urgency": "high"})

    def test_incorrect_weight_total_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            rank_candidates([], {"urgency": 0.5, "dependents": 0.4})

    def test_valid_normalized_weights_succeed(self) -> None:
        results = rank_candidates([], {"urgency": 1.0})
        self.assertEqual(results, [])

    def test_weight_total_within_transport_tolerance_succeeds(self) -> None:
        results = rank_candidates(
            [candidate(cycles_waited=0)],
            {"urgency": 0.5000005, "income_inverse": 0.5},
        )
        self.assertEqual(len(results), 1)


class ScoringTests(unittest.TestCase):
    def test_single_candidate_breakdown_and_decimal_sum(self) -> None:
        results = rank_candidates(
            [candidate(cycles_waited=1, verified_income=Decimal("25000"), urgency_level="high")],
            {"income_inverse": 0.5, "urgency": 0.5},
        )

        self.assertEqual(len(results), 1)
        ranked = results[0]

        self.assertEqual(ranked.rank, 1)
        self.assertEqual(list(ranked.score_breakdown.keys()), ["income_inverse", "urgency"])
        self.assertEqual(ranked.score_breakdown["income_inverse"], Decimal("0.375"))
        self.assertEqual(ranked.score_breakdown["urgency"], Decimal("0.375"))
        self.assertEqual(ranked.overall_priority_score, Decimal("0.75"))

        breakdown_sum = sum(ranked.score_breakdown.values(), Decimal("0"))
        self.assertLessEqual(
            abs(breakdown_sum - ranked.overall_priority_score),
            Decimal("0.000000001"),
        )

    def test_missing_non_inverted_optional_factor_contributes_zero(self) -> None:
        results = rank_candidates(
            [candidate(verified_household_size=None)],
            {"household_size": 1.0},
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].score_breakdown["household_size"], Decimal("0"))
        self.assertEqual(results[0].overall_priority_score, Decimal("0"))

    def test_missing_verified_income_contributes_neutral_midpoint(self) -> None:
        results = rank_candidates(
            [candidate(verified_income=None)],
            {"income_inverse": 1.0},
        )

        self.assertEqual(results[0].score_breakdown["income_inverse"], Decimal("0.5"))
        self.assertEqual(results[0].overall_priority_score, Decimal("0.5"))

    def test_missing_prior_assistance_contributes_neutral_midpoint(self) -> None:
        results = rank_candidates(
            [candidate(prior_assistance_count=None)],
            {"no_prior_assistance": 1.0},
        )

        self.assertEqual(results[0].score_breakdown["no_prior_assistance"], Decimal("0.5"))

    def test_empty_candidate_list_returns_empty(self) -> None:
        self.assertEqual(rank_candidates([], {"urgency": 1.0}), [])

    def test_single_candidate_gets_complete_breakdown_and_rank_one(self) -> None:
        results = rank_candidates(
            [candidate(urgency_level="critical")],
            {"urgency": 0.6, "cycles_waited": 0.4},
        )

        self.assertEqual(results[0].rank, 1)
        self.assertEqual(list(results[0].score_breakdown.keys()), ["urgency", "cycles_waited"])


class OrderingTests(unittest.TestCase):
    def test_multiple_candidates_rank_by_descending_score(self) -> None:
        results = rank_candidates(
            [
                candidate(candidate_id=CANDIDATE_A_ID, urgency_level="low"),
                candidate(candidate_id=CANDIDATE_B_ID, urgency_level="critical"),
                candidate(candidate_id=CANDIDATE_C_ID, urgency_level="medium"),
            ],
            {"urgency": 1.0},
        )

        self.assertEqual(
            [ranked.candidate_id for ranked in results],
            [CANDIDATE_B_ID, CANDIDATE_C_ID, CANDIDATE_A_ID],
        )
        self.assertEqual([ranked.rank for ranked in results], [1, 2, 3])

    def test_equal_scores_break_tie_by_cycles_waited(self) -> None:
        results = rank_candidates(
            [
                candidate(candidate_id=CANDIDATE_A_ID, cycles_waited=2),
                candidate(candidate_id=CANDIDATE_B_ID, cycles_waited=5),
            ],
            {"urgency": 1.0},
        )

        self.assertEqual([ranked.candidate_id for ranked in results], [CANDIDATE_B_ID, CANDIDATE_A_ID])
        self.assertEqual([ranked.rank for ranked in results], [1, 2])

    def test_equal_scores_and_wait_break_tie_by_candidate_id(self) -> None:
        results = rank_candidates(
            [
                candidate(candidate_id=CANDIDATE_B_ID, cycles_waited=0),
                candidate(candidate_id=CANDIDATE_A_ID, cycles_waited=0),
            ],
            {"urgency": 1.0},
        )

        self.assertEqual([ranked.candidate_id for ranked in results], [CANDIDATE_A_ID, CANDIDATE_B_ID])


class BehaviourTests(unittest.TestCase):
    def test_identical_inputs_produce_identical_results(self) -> None:
        candidates = [
            candidate(candidate_id=CANDIDATE_A_ID, urgency_level="high", cycles_waited=1),
            candidate(candidate_id=CANDIDATE_B_ID, urgency_level="low", cycles_waited=4),
        ]
        weights = {"urgency": 0.7, "cycles_waited": 0.3}

        self.assertEqual(rank_candidates(candidates, weights), rank_candidates(candidates, weights))

    def test_each_candidate_breakdown_reflects_only_its_own_facts(self) -> None:
        results = rank_candidates(
            [
                candidate(
                    candidate_id=CANDIDATE_A_ID,
                    verified_income=Decimal("20000"),
                    has_disability=True,
                ),
                candidate(
                    candidate_id=CANDIDATE_B_ID,
                    verified_income=Decimal("80000"),
                    has_disability=False,
                ),
            ],
            {"income_inverse": 0.5, "disability": 0.5},
        )

        by_id = {ranked.candidate_id: ranked for ranked in results}
        tolerance = Decimal("0.000000001")
        self.assertLessEqual(
            abs(by_id[CANDIDATE_A_ID].score_breakdown["income_inverse"] - Decimal("0.4")), tolerance
        )
        self.assertEqual(by_id[CANDIDATE_A_ID].score_breakdown["disability"], Decimal("0.5"))
        self.assertLessEqual(
            abs(by_id[CANDIDATE_B_ID].score_breakdown["income_inverse"] - Decimal("0.1")), tolerance
        )
        self.assertEqual(by_id[CANDIDATE_B_ID].score_breakdown["disability"], Decimal("0"))


if __name__ == "__main__":
    unittest.main()
