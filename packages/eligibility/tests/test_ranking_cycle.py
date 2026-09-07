"""Ranking-cycle orchestration tests: trigger 8's pure engine layer."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

PACKAGES_DIR = Path(__file__).resolve().parents[2]
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from eligibility.prioritization import VerifiedCandidate
from eligibility.ranking_cycle import CycleCandidate, RankingCycleConfig, run_ranking_cycle


RUN_DATE = date(2026, 9, 7)
PROGRAM_ID = UUID("10000000-0000-0000-0000-000000000001")
FRESH_ID = UUID("00000000-0000-0000-0000-000000000001")
STALE_ID = UUID("00000000-0000-0000-0000-000000000002")
APPROVED_ID = UUID("00000000-0000-0000-0000-000000000003")
NO_VALID_UNTIL_ID = UUID("00000000-0000-0000-0000-000000000004")
ROLLED_OVER_ID = UUID("00000000-0000-0000-0000-000000000005")


def cycle_candidate(
    candidate_id: UUID,
    *,
    status: str = "active",
    valid_until: date | None = None,
    urgency_level: str | None = None,
    cycles_waited: int = 0,
) -> CycleCandidate:
    return CycleCandidate(
        candidate=VerifiedCandidate(
            candidate_id=candidate_id,
            cycles_waited=cycles_waited,
            urgency_level=urgency_level,  # type: ignore[arg-type]
        ),
        status=status,  # type: ignore[arg-type]
        valid_until=valid_until,
    )


def config(**overrides: object) -> RankingCycleConfig:
    values: dict[str, object] = {
        "program_id": PROGRAM_ID,
        "run_date": RUN_DATE,
        "priority_weights": {"urgency": 1.0},
    }
    values.update(overrides)
    return RankingCycleConfig(**values)  # type: ignore[arg-type]


class RankingCycleTests(unittest.TestCase):
    def test_fresh_active_and_rolled_over_candidates_are_ranked(self) -> None:
        candidates = [
            cycle_candidate(FRESH_ID, valid_until=RUN_DATE, urgency_level="critical"),
            cycle_candidate(
                ROLLED_OVER_ID,
                status="rolled_over",
                valid_until=RUN_DATE + timedelta(days=1),
                urgency_level="low",
            ),
        ]

        result = run_ranking_cycle(candidates, config())

        self.assertEqual(
            [ranked.candidate_id for ranked in result.ranked_candidates],
            [FRESH_ID, ROLLED_OVER_ID],
        )
        self.assertEqual(result.pool_size, 2)
        self.assertEqual(result.expired_candidate_ids, [])

    def test_stale_verification_is_expired_not_ranked(self) -> None:
        candidates = [
            cycle_candidate(STALE_ID, valid_until=RUN_DATE - timedelta(days=1)),
        ]

        result = run_ranking_cycle(candidates, config())

        self.assertEqual(result.expired_candidate_ids, [STALE_ID])
        self.assertEqual(result.ranked_candidates, [])
        self.assertEqual(result.pool_size, 0)

    def test_non_rankable_statuses_are_skipped_entirely(self) -> None:
        candidates = [
            cycle_candidate(APPROVED_ID, status="approved", valid_until=RUN_DATE + timedelta(days=30)),
            cycle_candidate(APPROVED_ID, status="disbursed", valid_until=RUN_DATE + timedelta(days=30)),
            cycle_candidate(APPROVED_ID, status="expired", valid_until=RUN_DATE - timedelta(days=1)),
            cycle_candidate(APPROVED_ID, status="withdrawn", valid_until=RUN_DATE + timedelta(days=30)),
            cycle_candidate(APPROVED_ID, status="ranked", valid_until=RUN_DATE + timedelta(days=30)),
        ]

        result = run_ranking_cycle(candidates, config())

        self.assertEqual(result.ranked_candidates, [])
        self.assertEqual(result.expired_candidate_ids, [])
        self.assertEqual(result.pool_size, 0)

    def test_missing_valid_until_is_skipped_without_expiring(self) -> None:
        candidates = [cycle_candidate(NO_VALID_UNTIL_ID, valid_until=None)]

        result = run_ranking_cycle(candidates, config())

        self.assertEqual(result.ranked_candidates, [])
        self.assertEqual(result.expired_candidate_ids, [])

    def test_result_snapshots_weights_and_budget_capacity(self) -> None:
        weights = {"urgency": 0.6, "cycles_waited": 0.4}

        result = run_ranking_cycle(
            [],
            config(
                priority_weights=weights,
                budget_per_cycle=Decimal("50000"),
                capacity_per_cycle=10,
            ),
        )

        self.assertEqual(result.weights_snapshot, weights)
        self.assertEqual(result.budget_available, Decimal("50000"))
        self.assertEqual(result.capacity_available, 10)
        self.assertEqual(result.program_id, PROGRAM_ID)
        self.assertEqual(result.run_date, RUN_DATE)

    def test_empty_candidate_pool_produces_empty_cycle(self) -> None:
        result = run_ranking_cycle([], config())

        self.assertEqual(result.ranked_candidates, [])
        self.assertEqual(result.expired_candidate_ids, [])
        self.assertEqual(result.pool_size, 0)

    def test_ranked_order_follows_priority_scores(self) -> None:
        candidates = [
            cycle_candidate(FRESH_ID, valid_until=RUN_DATE, urgency_level="low"),
            cycle_candidate(ROLLED_OVER_ID, valid_until=RUN_DATE, urgency_level="critical"),
        ]

        result = run_ranking_cycle(candidates, config())

        self.assertEqual(
            [ranked.candidate_id for ranked in result.ranked_candidates],
            [ROLLED_OVER_ID, FRESH_ID],
        )
        self.assertEqual([ranked.rank for ranked in result.ranked_candidates], [1, 2])


if __name__ == "__main__":
    unittest.main()
