"""Unit tests for the staff-portal need rubric (app/portal/rubric.py).

Adapted from packages/eligibility/tests/test_prioritization.py -- the two
rubrics are functionally equivalent (same factors, same 'weights sum to 1,
entry_path never a factor' rules), but their MISSING-VALUE and TIE-BREAK
semantics differ on purpose, so these assert what score_need() actually
does rather than porting Rayan's expectations verbatim:

  * a missing WEIGHTED factor is a hard error here ("re-verify the
    candidate"), not silently filled with a neutral midpoint;
  * ties are broken in service.run_cycle() by applied_at then application
    id (End_to_End_Flows UC6), not by cycles_waited.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'services' / 'api'))
sys.path.insert(0, str(REPO / 'packages'))

from app.portal.rubric import DEFAULT_WEIGHTS, FACTOR_DEFINITIONS, score_need, validate_weights


def full(**overrides):
    facts = dict(verified_income=25_000, verified_household_size=6, dependents=3,
                 has_disability=False, prior_assistance_count=0, school_age_children=2,
                 urgency_level='high', chronic_illness_flag=False, cycles_waited=1)
    facts.update(overrides)
    return facts


class WeightValidation(unittest.TestCase):
    def test_default_weights_are_valid(self):
        self.assertEqual(validate_weights(dict(DEFAULT_WEIGHTS)), DEFAULT_WEIGHTS)

    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            validate_weights({'income_inverse': 0.5, 'dependents': 0.4})

    def test_negative_weight_rejected(self):
        with self.assertRaises(ValueError):
            validate_weights({'income_inverse': 1.5, 'dependents': -0.5})

    def test_unsupported_factor_rejected(self):
        with self.assertRaises(ValueError):
            validate_weights({'urgency': 0.5, 'favourite_colour': 0.5})

    def test_entry_path_rejected_by_name(self):
        with self.assertRaisesRegex(ValueError, 'entry_path'):
            validate_weights({'entry_path': 0.5, 'urgency': 0.5})

    def test_boolean_weight_rejected(self):
        with self.assertRaises(ValueError):
            validate_weights({'urgency': True})

    def test_non_numeric_weight_rejected(self):
        with self.assertRaises(ValueError):
            validate_weights({'urgency': 'high'})

    def test_every_defined_factor_is_weightable(self):
        even = {k: round(1 / len(FACTOR_DEFINITIONS), 6) for k in FACTOR_DEFINITIONS}
        even[next(iter(even))] += round(1 - sum(even.values()), 6)
        self.assertEqual(validate_weights(even), even)


class Scoring(unittest.TestCase):
    def test_breakdown_shape_and_points_arithmetic(self):
        weights = {'income_inverse': 0.6, 'urgency': 0.4}
        score, breakdown = score_need(**full(verified_income=0, urgency_level='critical'), weights=weights)
        self.assertEqual(set(breakdown), set(weights))
        for key, entry in breakdown.items():
            self.assertEqual(set(entry), {'value', 'weight', 'points', 'definition'})
            self.assertEqual(entry['definition'], FACTOR_DEFINITIONS[key])
            self.assertAlmostEqual(entry['points'], entry['value'] * entry['weight'] * 100, places=3)
        self.assertAlmostEqual(score, sum(e['points'] for e in breakdown.values()), places=3)
        self.assertAlmostEqual(score, 100.0, places=3)  # income_inverse=1, urgency=1

    def test_factor_normalisation(self):
        cases = [
            ({'income_inverse': 1.0}, dict(verified_income=25_000), 0.5),
            ({'household_size': 1.0}, dict(verified_household_size=5), 0.5),
            ({'dependents': 1.0}, dict(dependents=10), 1.0),
            ({'disability': 1.0}, dict(has_disability=True), 1.0),
            ({'no_prior_assistance': 1.0}, dict(prior_assistance_count=1), 0.5),
            ({'school_age_children': 1.0}, dict(school_age_children=3), 0.5),
            ({'urgency': 1.0}, dict(urgency_level='medium'), 0.5),
            ({'chronic_illness': 1.0}, dict(chronic_illness_flag=True), 1.0),
            ({'waiting_time': 1.0}, dict(cycles_waited=3), 0.5),
        ]
        for weights, facts, expected_value in cases:
            with self.subTest(factor=next(iter(weights))):
                _, breakdown = score_need(**full(**facts), weights=weights)
                self.assertAlmostEqual(breakdown[next(iter(weights))]['value'], expected_value, places=6)

    def test_missing_weighted_factor_is_a_hard_error(self):
        with self.assertRaisesRegex(ValueError, 'ranking factors'):
            score_need(**full(verified_household_size=None), weights={'household_size': 1.0})

    def test_missing_unweighted_factor_is_fine(self):
        score, _ = score_need(**full(verified_household_size=None), weights={'urgency': 1.0})
        self.assertGreater(score, 0)

    def test_more_need_scores_higher(self):
        weights = validate_weights(dict(DEFAULT_WEIGHTS))
        low, _ = score_need(**full(verified_income=90_000, dependents=0, prior_assistance_count=4,
                                   school_age_children=0, has_disability=False), weights=weights)
        high, _ = score_need(**full(verified_income=4_000, dependents=8, prior_assistance_count=0,
                                    school_age_children=5, has_disability=True), weights=weights)
        self.assertGreater(high, low)

    def test_scores_are_deterministic(self):
        weights = validate_weights(dict(DEFAULT_WEIGHTS))
        a = score_need(**full(), weights=weights)
        b = score_need(**full(), weights=weights)
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
