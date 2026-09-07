"""Framework-free duplicate-detection comparison (trigger 2).

The whole module is pure functions over strings: no database, no ORM, no
FastAPI. ``services/api`` (both the staff portal and the Supabase router)
reads the candidate rows itself and calls :func:`compare` per pair.

Order matters, and mirrors ``packages/dedup/README.md``:

1. **CNIC exact match** -- a national ID collision is a near-certain duplicate,
   scored 100. Compared on digits only (:func:`normalize_cnic`) so
   ``35201-1234567-1`` and ``3520112345671`` are the same person.
2. **Fuzzy name / phone** -- ``max`` of a token-sorted name ratio and a plain
   phone-digit ratio, on RapidFuzz's 0-100 scale. At or above
   :data:`FUZZY_THRESHOLD` the pair is flagged for a human to look at.

Nothing here decides anything: a positive result is a *flag*, written at
``status='pending'`` for the staff duplicate queue.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

# 0-100 RapidFuzz scale. Deliberately high: a flag pulls a staff member away
# to compare two records by hand, so a false positive has a real cost. Tune
# with real data, not a guess.
FUZZY_THRESHOLD = 85


@dataclass(frozen=True)
class DuplicateSignal:
    """One suspected-duplicate pairing. ``matched_on`` names the rule that
    fired, for the audit trail and the staff queue's "Detected by" column."""

    score: float
    matched_on: str  # 'cnic_exact' | 'name_phone_fuzzy'


def normalize_cnic(cnic: str | None) -> str | None:
    """Digits only. ``None``/blank -> ``None`` (no CNIC is not a match)."""
    if not cnic:
        return None
    digits = "".join(ch for ch in cnic if ch.isdigit())
    return digits or None


def same_cnic(a: str | None, b: str | None) -> bool:
    """True only when both sides have a CNIC and their digits are identical."""
    na, nb = normalize_cnic(a), normalize_cnic(b)
    return na is not None and na == nb


def _phone_digits(phone: str | None) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def compare(
    *,
    name_a: str | None,
    phone_a: str | None,
    cnic_a: str | None,
    name_b: str | None,
    phone_b: str | None,
    cnic_b: str | None,
) -> DuplicateSignal | None:
    """Compare two profiles. Returns the strongest signal, or ``None`` if the
    pair is not similar enough to flag."""

    if same_cnic(cnic_a, cnic_b):
        return DuplicateSignal(score=100.0, matched_on="cnic_exact")

    name_score = fuzz.token_sort_ratio(name_a or "", name_b or "")
    digits_a, digits_b = _phone_digits(phone_a), _phone_digits(phone_b)
    phone_score = fuzz.ratio(digits_a, digits_b) if digits_a and digits_b else 0
    combined = max(name_score, phone_score)

    if combined >= FUZZY_THRESHOLD:
        return DuplicateSignal(score=float(combined), matched_on="name_phone_fuzzy")
    return None
