"""Duplicate-detection primitives (trigger 2).

Pure, framework-free comparison helpers. CNIC exact match first, then a
RapidFuzz name/phone comparison -- no vector similarity (``beneficiary_profiles``
carries no embedding). Callers own the database: they read candidate rows, call
:func:`compare`, and write ``duplicate_flags`` at ``status='pending'`` for a
staff queue. Merging is always a manual decision, never automatic.
"""

from .matching import (
    FUZZY_THRESHOLD,
    DuplicateSignal,
    compare,
    normalize_cnic,
    same_cnic,
)

__all__ = [
    "FUZZY_THRESHOLD",
    "DuplicateSignal",
    "compare",
    "normalize_cnic",
    "same_cnic",
]
