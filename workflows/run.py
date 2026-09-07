"""CLI entrypoint for the scheduled jobs — what a scheduler (or you) runs.

    python -m workflows.run ranking-cycles     # trigger 8, schedule bi-weekly
    python -m workflows.run marketplace-sweep   # trigger 9, schedule daily
    python -m workflows.run triggers            # print the trigger registry

Exit code is non-zero if the job raised, so a failed run is visible to whatever scheduler invoked it.
"""

from __future__ import annotations

import json
import sys

from . import scheduled, triggers

JOBS = {
    "ranking-cycles": scheduled.run_ranking_cycles,
    "marketplace-sweep": scheduled.run_marketplace_sweep,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    command = argv[0]
    if command == "triggers":
        print(triggers.describe())
        return 0
    job = JOBS.get(command)
    if job is None:
        print(f"unknown job: {command}\n{__doc__}", file=sys.stderr)
        return 2
    result = job()
    print(json.dumps({"job": command, "result": result}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
