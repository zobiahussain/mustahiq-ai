"""The two scheduled jobs (triggers 8 and 9).

Kept as plain importable functions so they can be unit-tested and called from
anywhere; ``workflows/run.py`` is the thin CLI a scheduler (or you) invokes.

Neither job makes an allocation or contacts anyone:

* trigger 8 ranks the verified pool and stops — a human reviews and disburses
  (SRS: never auto-enroll);
* trigger 9 only flips stale rows to ``expired``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _dir in (_ROOT / "services" / "api", _ROOT / "packages", _ROOT / "packages" / "rag", _ROOT / "packages" / "marketplace"):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))


def run_ranking_cycles() -> dict:
    """Trigger 8 — bi-weekly. Rank every programme whose cycle is due.

    Uses the same staff-portal database the API does (Supabase via
    ``DATABASE_URL``, or the SQLite demo when ``PORTAL_DEMO_MODE=true``).
    """
    from app.core.db import SessionLocal
    from app.portal import service as portal

    with SessionLocal() as db:
        summary = portal.run_due_cycles(db)
        db.commit()
    return summary


def run_marketplace_sweep() -> dict:
    """Trigger 9 — daily. Expire stale marketplace matches (7 days) and
    unconfirmed listings (6 months). Operates on the marketplace Supabase
    (``DATABASE_URL``)."""
    from lifecycle import expire_stale_listings, expire_stale_matches

    return {
        "matches_expired": expire_stale_matches(),
        "listings_expired": expire_stale_listings(),
    }
