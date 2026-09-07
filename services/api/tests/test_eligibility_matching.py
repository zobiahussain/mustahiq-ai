"""Unit tests for the API-side eligibility discovery adapter."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_DIR = REPO_ROOT / "packages"
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

from app.services.eligibility_matching import (
    discovery_program_from_row,
    get_persisted_matches,
    refresh_beneficiary_matches,
)


BENEFICIARY_ID = UUID("00000000-0000-0000-0000-000000000001")
PROGRAM_ID = UUID("10000000-0000-0000-0000-000000000001")


class FakeResult:
    def __init__(self, *, one=None, many=None) -> None:
        self._one = one
        self._many = many if many is not None else []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class FakeDb:
    def __init__(self, profile_row: dict, program_rows: list[dict]) -> None:
        self.profile_row = profile_row
        self.program_rows = program_rows
        self.calls: list[tuple[str, dict | None]] = []
        self.committed = False

    def execute(self, statement, parameters=None):
        query = str(statement)
        self.calls.append((query, parameters))
        if "select * from beneficiary_profiles" in query:
            return FakeResult(one=self.profile_row)
        if "from programs" in query and "where active = true" in query:
            return FakeResult(many=self.program_rows)
        return FakeResult()

    def commit(self) -> None:
        self.committed = True


class RecordingScorer:
    def __init__(self, score: float = 0.7) -> None:
        self.score = score
        self.calls = 0

    def predict_confidence(self, feature_row: dict) -> float:
        self.calls += 1
        return self.score


def profile_row(**updates: object) -> dict:
    values: dict[str, object] = {
        "id": BENEFICIARY_ID,
        "full_name": "Verified Test Person",
        "employment_status": "unemployed",
        "monthly_income": Decimal("25000"),
        "household_size": 4,
        "dependents": 2,
    }
    values.update(updates)
    return values


def program_row(**updates: object) -> dict:
    values: dict[str, object] = {
        "id": PROGRAM_ID,
        "name": "Bano Qabil Program",
        "domain": "bano_qabil",
        "criteria_structured": {
            "hard_rules": [
                {
                    "rule_id": "BANO-01",
                    "field": "employment_status",
                    "operator": "==",
                    "value": "unemployed",
                    "description": "Currently unemployed",
                }
            ]
        },
        "requires_explicit_application": False,
    }
    values.update(updates)
    return values


class EligibilityMatchingAdapterTests(unittest.TestCase):
    def test_active_program_row_becomes_discovery_program(self) -> None:
        program = discovery_program_from_row(program_row())
        self.assertEqual(program.program_id, str(PROGRAM_ID))
        self.assertEqual(program.rules[0].rule_id, "BANO-01")

    def test_active_program_without_confirmed_rules_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "hard_rules"):
            discovery_program_from_row(program_row(criteria_structured={}))

    def test_refresh_persists_only_actionable_results_and_commits(self) -> None:
        db = FakeDb(profile_row(), [program_row()])
        scorer = RecordingScorer()

        results = refresh_beneficiary_matches(db, BENEFICIARY_ID, scorer)  # type: ignore[arg-type]

        self.assertEqual(results[0].status, "pending_review")
        self.assertEqual(scorer.calls, 1)
        inserts = [query for query, _ in db.calls if "insert into match_records" in query]
        self.assertEqual(len(inserts), 1)
        self.assertIn("where match_records.status in ('pending_review', 'suppressed')", inserts[0])
        self.assertTrue(db.committed)

    def test_non_actionable_result_is_not_inserted(self) -> None:
        db = FakeDb(profile_row(employment_status="salaried"), [program_row()])
        scorer = RecordingScorer()

        results = refresh_beneficiary_matches(db, BENEFICIARY_ID, scorer)  # type: ignore[arg-type]

        self.assertEqual(results[0].status, "not_eligible")
        self.assertEqual(scorer.calls, 0)
        self.assertFalse(any("insert into match_records" in query for query, _ in db.calls))

    def test_reading_persisted_matches_does_not_run_discovery(self) -> None:
        class ReadDb:
            def execute(self, statement, parameters=None):
                return FakeResult(
                    many=[
                        {
                            "program_id": PROGRAM_ID,
                            "program_name": "Bano Qabil Program",
                            "score": Decimal("0.7"),
                            "reason": "Suggested because it meets: Currently unemployed. Verification confidence: high.",
                            "status": "pending_review",
                        }
                    ]
                )

        matches = get_persisted_matches(ReadDb(), BENEFICIARY_ID)  # type: ignore[arg-type]
        self.assertEqual(matches[0]["program_id"], PROGRAM_ID)
        self.assertEqual(matches[0]["status"], "pending_review")


if __name__ == "__main__":
    unittest.main()
