"""Duplicate-detection comparison tests (packages/dedup)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dedup import FUZZY_THRESHOLD, compare, normalize_cnic, same_cnic


class NormalizeCnic(unittest.TestCase):
    def test_strips_formatting(self):
        self.assertEqual(normalize_cnic("35201-1234567-1"), "3520112345671")

    def test_blank_and_none_are_none(self):
        self.assertIsNone(normalize_cnic(None))
        self.assertIsNone(normalize_cnic("   "))
        self.assertIsNone(normalize_cnic("--"))

    def test_same_cnic_ignores_formatting(self):
        self.assertTrue(same_cnic("35201-1234567-1", "3520112345671"))
        self.assertFalse(same_cnic("3520112345671", "3520112345672"))
        self.assertFalse(same_cnic(None, None))


class Compare(unittest.TestCase):
    def test_cnic_exact_wins_and_scores_100(self):
        signal = compare(
            name_a="Totally Different", phone_a="+92300", cnic_a="35201-1234567-1",
            name_b="Someone Else", phone_b="+92311", cnic_b="3520112345671",
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal.matched_on, "cnic_exact")
        self.assertEqual(signal.score, 100.0)

    def test_identical_name_is_flagged(self):
        signal = compare(
            name_a="Fatima Bibi", phone_a=None, cnic_a=None,
            name_b="Fatima Bibi", phone_b=None, cnic_b=None,
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal.matched_on, "name_phone_fuzzy")
        self.assertGreaterEqual(signal.score, FUZZY_THRESHOLD)

    def test_reordered_name_still_flagged(self):
        signal = compare(
            name_a="Bibi Fatima", phone_a=None, cnic_a=None,
            name_b="Fatima Bibi", phone_b=None, cnic_b=None,
        )
        self.assertIsNotNone(signal)

    def test_same_phone_different_name_is_flagged_on_phone(self):
        signal = compare(
            name_a="Ali Hassan", phone_a="+92 300 1234567", cnic_a=None,
            name_b="A. Hassan", phone_b="03001234567", cnic_b=None,
        )
        self.assertIsNotNone(signal)

    def test_unrelated_people_are_not_flagged(self):
        self.assertIsNone(compare(
            name_a="Fatima Bibi", phone_a="+923001111111", cnic_a="3520100000001",
            name_b="Muhammad Aslam", phone_b="+923339999999", cnic_b="3520100000002",
        ))

    def test_missing_phones_do_not_false_match_on_empty_string(self):
        # both phones absent -> phone score must be 0, not a 100 "empty==empty"
        self.assertIsNone(compare(
            name_a="Ada", phone_a=None, cnic_a=None,
            name_b="Zed", phone_b=None, cnic_b=None,
        ))


if __name__ == "__main__":
    unittest.main()
