"""The 9 triggers, what each does, and where its logic lives.

This project does NOT run a workflow engine (LlamaIndex Workflows was the
original plan; it turned out to be orchestration for multi-step LLM agents,
which none of these are -- every one is a single deterministic function call).
So "the trigger layer" is really two things:

* **Events (1-7)** -- fire synchronously inside the API request that causes
  them. Registration-time discovery is milliseconds and deterministic; the
  re-scan triggers (5, 6) touch every beneficiary but still run inline because
  no queue/worker infra exists and the caseload is hackathon-scale. This is
  the answer to CLAUDE.md open question #3 for the hackathon: inline events,
  cron for the scheduled jobs.
* **Scheduled (8, 9)** -- no event to hang off, so :mod:`workflows.scheduled`
  runs them from ``python -m workflows.run`` on any scheduler.

``TRIGGERS`` below is the authoritative list (Team_Work_Division.md section 3,
End_to_End_Flows.md).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trigger:
    number: int
    name: str
    kind: str  # 'event' | 'scheduled'
    fires_on: str
    does: str
    implemented_in: str


TRIGGERS: tuple[Trigger, ...] = (
    Trigger(1, "Beneficiary registered", "event",
            "POST /portal/profiles (and profile edit)",
            "Score the profile against every active programme (rules eliminate, XGBoost ranks confidence).",
            "services/api/app/portal/service.py::discover -> packages/eligibility/discovery.py"),
    Trigger(2, "Profile created", "event",
            "POST /portal/profiles",
            "Duplicate detection: CNIC exact (rejected at creation), then RapidFuzz name/phone -> pending duplicate_flags.",
            "services/api/app/portal/service.py::detect_duplicates -> packages/dedup/matching.py"),
    Trigger(3, "Match pooled by staff", "event",
            "POST /portal/matches/{id}/review {action: pooled}",
            "Add the suggestion to the Potentially Eligible Pool (awaiting_outreach). Nobody is contacted.",
            "services/api/app/portal/service.py::review_match"),
    Trigger(4, "Verification recorded", "event",
            "POST /portal/verifications",
            "Create or link the application; a failed verification exits the pool.",
            "services/api/app/portal/service.py::verify"),
    Trigger(5, "New programme added", "event",
            "POST /portal/programs",
            "Re-scan every existing beneficiary against the new programme (day-one/day-five pattern).",
            "services/api/app/portal/service.py (create_program re-runs discover per profile)"),
    Trigger(6, "Criteria edited", "event",
            "PUT /portal/programs/{id}",
            "Re-scan every existing beneficiary; expire applications a tightened rule now fails.",
            "services/api/app/portal/service.py (edit_program)"),
    Trigger(7, "Listing created or edited", "event",
            "POST /listing, PUT /listing/{id} (marketplace API)",
            "Marketplace matching (3 models -> filter -> similarity -> proximity), then notify both parties by SMS/email. Runs as a FastAPI BackgroundTask.",
            "packages/marketplace/matching_pipeline.py::match_and_notify"),
    Trigger(8, "Ranking cycle due", "scheduled",
            "scheduled (bi-weekly) -- python -m workflows.run ranking-cycles",
            "For every active programme whose cycle is due: expire stale verifications, score and rank the verified pool with the transparent rubric. Stops at status='ranked' -- a human reviews and allocates.",
            "workflows/scheduled.py::run_ranking_cycles -> services/api/app/portal/service.py::run_due_cycles"),
    Trigger(9, "Daily marketplace sweep", "scheduled",
            "scheduled (daily) -- python -m workflows.run marketplace-sweep",
            "Expire marketplace matches unanswered for 7 days and listings unconfirmed for 6 months.",
            "workflows/scheduled.py::run_marketplace_sweep -> packages/marketplace/lifecycle.py"),
)


def describe() -> str:
    lines = []
    for trig in TRIGGERS:
        lines.append(f"[{trig.number}] {trig.name}  ({trig.kind}, fires on: {trig.fires_on})")
        lines.append(f"     {trig.does}")
        lines.append(f"     impl: {trig.implemented_in}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
