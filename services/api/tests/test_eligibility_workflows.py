"""Unit tests for API-callable eligibility trigger handlers."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_DIR = REPO_ROOT / "packages"
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from app.services.eligibility_workflows import (
    on_profile_created_or_updated,
    on_program_added_or_criteria_changed,
    run_biweekly_ranking_cycle,
)


PROGRAM_ID = UUID("10000000-0000-0000-0000-000000000001")
ACTIVE_ID = UUID("00000000-0000-0000-0000-000000000001")
EXPIRED_ID = UUID("00000000-0000-0000-0000-000000000002")
RUN_DATE = date(2026, 9, 7)


class FakeResult:
    def __init__(self, *, one=None, many=None) -> None:
        self._one = one
        self._many = many if many is not None else []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class FakeRankingDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []
        self.committed = False

    def execute(self, statement, parameters=None):
        query = str(statement)
        self.calls.append((query, parameters))
        if "select id, priority_weights" in query:
            return FakeResult(
                one={
                    "id": PROGRAM_ID,
                    "priority_weights": {"urgency": 1.0},
                    "budget_per_cycle": Decimal("50000"),
                    "capacity_per_cycle": 1,
                }
            )
        if "from applications a" in query:
            return FakeResult(
                many=[
                    {
                        "candidate_id": ACTIVE_ID,
                        "status": "active",
                        "cycles_waited": 0,
                        "valid_until": RUN_DATE + timedelta(days=1),
                        "verified_income": Decimal("20000"),
                        "verified_household_size": 4,
                        "urgency_level": "critical",
                        "program_specific_data": {},
                    },
                    {
                        "candidate_id": EXPIRED_ID,
                        "status": "rolled_over",
                        "cycles_waited": 2,
                        "valid_until": RUN_DATE - timedelta(days=1),
                        "verified_income": Decimal("10000"),
                        "verified_household_size": 5,
                        "urgency_level": "high",
                        "program_specific_data": {},
                    },
                ]
            )
        return FakeResult()

    def commit(self) -> None:
        self.committed = True


class EligibilityWorkflowTests(unittest.TestCase):
    def test_profile_event_delegates_to_all_program_refresh(self) -> None:
        scorer = object()
        with patch("app.services.eligibility_workflows.refresh_beneficiary_matches", return_value=["result"]) as refresh:
            result = on_profile_created_or_updated(object(), ACTIVE_ID, scorer)  # type: ignore[arg-type]
        self.assertEqual(result, ["result"])
        refresh.assert_called_once_with(unittest.mock.ANY, ACTIVE_ID, scorer)

    def test_program_event_delegates_to_single_program_rescan(self) -> None:
        scorer = object()
        with patch("app.services.eligibility_workflows.refresh_program_matches", return_value={}) as refresh:
            result = on_program_added_or_criteria_changed(object(), PROGRAM_ID, scorer)  # type: ignore[arg-type]
        self.assertEqual(result, {})
        refresh.assert_called_once_with(unittest.mock.ANY, PROGRAM_ID, scorer)

    def test_biweekly_trigger_expires_stale_rows_persists_ranks_and_audits_cycle(self) -> None:
        db = FakeRankingDb()
        result = run_biweekly_ranking_cycle(db, PROGRAM_ID, RUN_DATE)  # type: ignore[arg-type]

        self.assertEqual(result.pool_size, 1)
        self.assertEqual(result.ranked_candidates[0].candidate_id, ACTIVE_ID)
        self.assertEqual(result.expired_candidate_ids, [EXPIRED_ID])
        self.assertEqual(result.capacity_available, 1)
        self.assertTrue(db.committed)

        queries = [query for query, _ in db.calls]
        self.assertTrue(any("set status = 'expired'" in query for query in queries))
        self.assertTrue(any("rank_in_cycle" in query and "set need_score" in query for query in queries))
        self.assertTrue(any("insert into ranking_cycles" in query for query in queries))


if __name__ == "__main__":
    unittest.main()
