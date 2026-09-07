"""Transparent need rubric. No model, discovery confidence, or entry path input.

These normalization caps are DEMO POLICY, not asserted Al-Khidmat policy. An
administrator reviews the displayed definitions and weights before running a cycle.
"""
import math

FACTOR_DEFINITIONS = {
    'income_inverse': '1 − min(verified income / PKR 50,000, 1)',
    'household_size': 'min(verified household size / 10, 1)',
    'dependents': 'min(dependents / 10, 1)',
    'disability': '1 if disability confirmed, otherwise 0',
    'no_prior_assistance': '1 / (1 + prior assistance count)',
    'school_age_children': 'min(school-age children / 6, 1)',
    'urgency': 'low 0.25, medium 0.50, high 0.75, critical 1.00',
    'chronic_illness': '1 if chronic illness confirmed, otherwise 0',
    'waiting_time': 'min(cycles waited / 6, 1)',
}
DEFAULT_WEIGHTS = {'income_inverse': .30, 'dependents': .20, 'disability': .15, 'no_prior_assistance': .20, 'school_age_children': .15}


def validate_weights(weights):
    if not weights or set(weights) - set(FACTOR_DEFINITIONS):
        raise ValueError('Choose only the supported need factors; entry_path and discovery confidence are never permitted.')
    if any(isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError('Weights must be finite, non-negative numbers.')
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-6):
        raise ValueError('Weights must add up to 100%.')
    return weights


def score_need(*, verified_income, dependents, has_disability, prior_assistance_count,
               school_age_children, urgency_level, chronic_illness_flag, cycles_waited, weights,
               verified_household_size=None):
    validate_weights(weights)
    raw = {'income_inverse': verified_income, 'household_size': verified_household_size,
           'dependents': dependents, 'disability': has_disability,
           'no_prior_assistance': prior_assistance_count, 'school_age_children': school_age_children,
           'urgency': urgency_level, 'chronic_illness': chronic_illness_flag, 'waiting_time': cycles_waited}
    missing = [key for key, weight in weights.items() if weight > 0 and raw[key] is None]
    if missing:
        raise ValueError('Complete verified ranking factors: ' + ', '.join(missing))
    values = {
        'income_inverse': max(0, 1 - min((verified_income or 0) / 50000, 1)),
        'household_size': min((verified_household_size or 0) / 10, 1),
        'dependents': min((dependents or 0) / 10, 1), 'disability': float(bool(has_disability)),
        'no_prior_assistance': 1 / (1 + (prior_assistance_count or 0)),
        'school_age_children': min((school_age_children or 0) / 6, 1),
        'urgency': {'low': .25, 'medium': .5, 'high': .75, 'critical': 1}.get(urgency_level, 0),
        'chronic_illness': float(bool(chronic_illness_flag)), 'waiting_time': min((cycles_waited or 0) / 6, 1),
    }
    breakdown = {key: {'value': round(values[key], 6), 'weight': weight,
                       'points': round(values[key] * weight * 100, 4), 'definition': FACTOR_DEFINITIONS[key]}
                 for key, weight in weights.items()}
    return round(sum(v['points'] for v in breakdown.values()), 4), breakdown
