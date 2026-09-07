"""Unit tests for the programme and profile endpoints that fire triggers 1, 5, 6, 8."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_DIR = REPO_ROOT / "packages"
if str(PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGES_DIR))

# Importing the routers pulls in app.core.config, which requires these even
# though these unit tests never connect to Supabase or the database.
os.environ.setdefault("DATABASE_URL", "postgresql://localhost/mustahiq_test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

from fastapi import HTTPException

from app.routers.beneficiaries import update_beneficiary
from app.routers.programs import create_program, run_program_ranking_cycle, update_program
from app.schemas.beneficiary import BeneficiaryUpdate
from app.schemas.program import ProgramCreate, ProgramUpdate, RankingCycleRequest


BENEFICIARY_ID = UUID("00000000-0000-0000-0000-000000000001")
PROGRAM_ID = UUID("10000000-0000-0000-0000-000000000001")
ACTIVE_ID = UUID("00000000-0000-0000-0000-000000000001")
EXPIRED_ID = UUID("00000000-0000-0000-0000-000000000002")
RUN_DATE = date(2026, 9, 7)

STAFF = {"id": UUID("00000000-0000-0000-0000-000000000099"), "role": "department_admin"}

HARD_RULES = {
    "hard_rules": [
        {
            "rule_id": "BANO-01",
            "field": "employment_status",
            "operator": "==",
            "value": "unemployed",
            "description": "Currently unemployed",
        }
    ]
}

PRIORITY_WEIGHTS = {"urgency": 1.0}


class FakeResult:
    def __init__(self, *, one=None, many=None) -> None:
        self._one = one
        self._many = many if many is not None else []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class FakeDb:
    """Dispatches by SQL substring, in the order the endpoints execute."""

    def __init__(self, *, program_row=None, profile_rows=None, application_rows=None,
                 updated_profile_row=None, updated_program_row=None) -> None:
        self.program_row = program_row
        self.profile_rows = profile_rows if profile_rows is not None else []
        self.application_rows = application_rows if application_rows is not None else []
        self.updated_profile_row = updated_profile_row
        self.updated_program_row = updated_program_row
        self.calls: list[tuple[str, dict | None]] = []
        self.committed = False

    def execute(self, statement, parameters=None):
        query = str(statement)
        self.calls.append((query, parameters))
        if "insert into programs" in query:
            return FakeResult(one=self.program_row)
        if "update programs" in query:
            return FakeResult(one=self.updated_program_row)
        if "update beneficiary_profiles" in query:
            return FakeResult(one=self.updated_profile_row)
        if "select * from beneficiary_profiles where id" in query:
            return FakeResult(one=self.updated_profile_row)
        if "select * from beneficiary_profiles order by id" in query:
            return FakeResult(many=self.profile_rows)
        if "from programs" in query and "where id = :program_id" in query:
            return FakeResult(one=self.program_row)
        if "from programs" in query and "active = true" in query:
            return FakeResult(many=[self.program_row])
        if "from applications a" in query:
            return FakeResult(many=self.application_rows)
        return FakeResult()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


class RecordingScorer:
    def __init__(self, score: float = 0.7) -> None:
        self.score = score
        self.calls = 0

    def predict_confidence(self, feature_row: dict) -> float:
        self.calls += 1
        return self.score


def program_row(**updates: object) -> dict:
    values: dict[str, object] = {
        "id": PROGRAM_ID,
        "name": "Bano Qabil Program",
        "domain": "bano_qabil",
        "criteria_structured": HARD_RULES,
        "requires_explicit_application": False,
        "department_id": None,
        "description": None,
        "active": True,
        "budget_per_cycle": Decimal("50000"),
        "capacity_per_cycle": 1,
        "priority_weights": PRIORITY_WEIGHTS,
        "created_at": datetime(2026, 9, 1, 12, 0, 0),
        "updated_at": datetime(2026, 9, 1, 12, 0, 0),
    }
    values.update(updates)
    return values


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


def application_row(**updates: object) -> dict:
    values: dict[str, object] = {
        "candidate_id": ACTIVE_ID,
        "status": "active",
        "cycles_waited": 0,
        "valid_until": RUN_DATE + timedelta(days=1),
        "verified_income": Decimal("20000"),
        "verified_household_size": 4,
        "urgency_level": "critical",
        "program_specific_data": {},
    }
    values.update(updates)
    return values


class CreateProgramTriggerTests(unittest.TestCase):
    def test_new_program_rescans_every_profile_and_reports_actionable_matches(self) -> None:
        db = FakeDb(program_row=program_row(), profile_rows=[profile_row()])
        scorer = RecordingScorer()

        response = create_program(
            payload=ProgramCreate(
                name="Bano Qabil Program",
                domain="bano_qabil",
                criteria_structured=HARD_RULES,
                priority_weights=PRIORITY_WEIGHTS,
            ),
            db=db,  # type: ignore[arg-type]
            staff=STAFF,  # type: ignore[arg-type]
            scorer=scorer,  # type: ignore[arg-type]
        )

        self.assertEqual(response["rescan"].profiles_scanned, 1)
        self.assertEqual(response["rescan"].actionable_matches, 1)
        self.assertEqual(scorer.calls, 1)
        self.assertTrue(db.committed)
        inserts = [query for query, _ in db.calls if "insert into match_records" in query]
        self.assertEqual(len(inserts), 1)

    def test_invalid_criteria_is_rejected_at_the_boundary(self) -> None:
        with self.assertRaises(ValueError):
            ProgramCreate(
                name="Broken Program",
                domain="education",
                criteria_structured={"hard_rules": []},
            )

    def test_entry_path_weights_are_rejected_at_the_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "entry_path"):
            ProgramCreate(
                name="Unfair Program",
                domain="education",
                criteria_structured=HARD_RULES,
                priority_weights={"entry_path": 0.5, "urgency": 0.5},
            )


class UpdateProgramTriggerTests(unittest.TestCase):
    def test_criteria_change_fires_program_rescan(self) -> None:
        db = FakeDb(
            program_row=program_row(),
            updated_program_row=program_row(),
            profile_rows=[profile_row()],
        )
        scorer = RecordingScorer()

        response = update_program(
            program_id=str(PROGRAM_ID),
            payload=ProgramUpdate(criteria_structured=HARD_RULES),
            db=db,  # type: ignore[arg-type]
            staff=STAFF,  # type: ignore[arg-type]
            scorer=scorer,  # type: ignore[arg-type]
        )

        self.assertEqual(response["rescan"].profiles_scanned, 1)
        self.assertEqual(scorer.calls, 1)
        self.assertTrue(any("update programs" in query for query, _ in db.calls))

    def test_name_only_change_does_not_rescan(self) -> None:
        db = FakeDb(updated_program_row=program_row())
        scorer = RecordingScorer()

        response = update_program(
            program_id=str(PROGRAM_ID),
            payload=ProgramUpdate(name="Renamed Program"),
            db=db,  # type: ignore[arg-type]
            staff=STAFF,  # type: ignore[arg-type]
            scorer=scorer,  # type: ignore[arg-type]
        )

        self.assertIsNone(response["rescan"])
        self.assertEqual(scorer.calls, 0)
        self.assertFalse(any("select * from beneficiary_profiles" in query for query, _ in db.calls))

    def test_unknown_program_returns_404(self) -> None:
        db = FakeDb(updated_program_row=None)

        with self.assertRaises(HTTPException) as context:
            update_program(
                program_id=str(PROGRAM_ID),
                payload=ProgramUpdate(name="Renamed Program"),
                db=db,  # type: ignore[arg-type]
                staff=STAFF,  # type: ignore[arg-type]
                scorer=RecordingScorer(),  # type: ignore[arg-type]
            )
        self.assertEqual(context.exception.status_code, 404)

    def test_malformed_program_id_returns_422(self) -> None:
        with self.assertRaises(HTTPException) as context:
            update_program(
                program_id="not-a-uuid",
                payload=ProgramUpdate(name="Renamed Program"),
                db=FakeDb(),  # type: ignore[arg-type]
                staff=STAFF,  # type: ignore[arg-type]
                scorer=RecordingScorer(),  # type: ignore[arg-type]
            )
        self.assertEqual(context.exception.status_code, 422)


class RankingCycleEndpointTests(unittest.TestCase):
    def test_ranking_cycle_endpoint_expires_persists_and_audits(self) -> None:
        db = FakeDb(
            program_row=program_row(),
            application_rows=[
                application_row(),
                application_row(
                    candidate_id=EXPIRED_ID,
                    status="rolled_over",
                    cycles_waited=2,
                    valid_until=RUN_DATE - timedelta(days=1),
                    urgency_level="high",
                ),
            ],
        )

        response = run_program_ranking_cycle(
            program_id=str(PROGRAM_ID),
            payload=RankingCycleRequest(run_date=RUN_DATE),
            db=db,  # type: ignore[arg-type]
            staff=STAFF,  # type: ignore[arg-type]
        )

        self.assertEqual(response.pool_size, 1)
        self.assertEqual(response.ranked_candidates[0].candidate_id, ACTIVE_ID)
        self.assertEqual(response.ranked_candidates[0].rank, 1)
        self.assertEqual(response.expired_application_ids, [EXPIRED_ID])
        self.assertEqual(response.weights_snapshot, PRIORITY_WEIGHTS)
        self.assertTrue(db.committed)
        queries = [query for query, _ in db.calls]
        self.assertTrue(any("set status = 'expired'" in query for query in queries))
        self.assertTrue(any("insert into ranking_cycles" in query for query in queries))

    def test_unknown_active_program_returns_404(self) -> None:
        db = FakeDb(program_row=None)

        with self.assertRaises(HTTPException) as context:
            run_program_ranking_cycle(
                program_id=str(PROGRAM_ID),
                payload=RankingCycleRequest(run_date=RUN_DATE),
                db=db,  # type: ignore[arg-type]
                staff=STAFF,  # type: ignore[arg-type]
            )
        self.assertEqual(context.exception.status_code, 404)


class UpdateBeneficiaryTriggerTests(unittest.TestCase):
    def test_profile_update_re_fires_discovery_against_all_active_programs(self) -> None:
        db = FakeDb(
            program_row=program_row(),
            updated_profile_row=profile_row(),
        )
        scorer = RecordingScorer()

        response = update_beneficiary(
            beneficiary_id=str(BENEFICIARY_ID),
            payload=BeneficiaryUpdate(monthly_income=20000),
            db=db,  # type: ignore[arg-type]
            staff=STAFF,  # type: ignore[arg-type]
            scorer=scorer,  # type: ignore[arg-type]
        )

        self.assertEqual(response["id"], BENEFICIARY_ID)
        self.assertEqual(scorer.calls, 1)
        self.assertTrue(any("update beneficiary_profiles" in query for query, _ in db.calls))
        self.assertTrue(any("insert into match_records" in query for query, _ in db.calls))
        self.assertTrue(db.committed)

    def test_unknown_beneficiary_returns_404(self) -> None:
        db = FakeDb(updated_profile_row=None)

        with self.assertRaises(HTTPException) as context:
            update_beneficiary(
                beneficiary_id=str(BENEFICIARY_ID),
                payload=BeneficiaryUpdate(monthly_income=20000),
                db=db,  # type: ignore[arg-type]
                staff=STAFF,  # type: ignore[arg-type]
                scorer=RecordingScorer(),  # type: ignore[arg-type]
            )
        self.assertEqual(context.exception.status_code, 404)

    def test_empty_update_payload_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BeneficiaryUpdate()


if __name__ == "__main__":
    unittest.main()
