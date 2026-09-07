"""Synthetic profiles, the demo programme catalogue, and noisy verification labels.

The programme catalogue here is Al-Khidmat's seven real areas of work, each with
two-to-three sub-programmes (22 in total). It is shared verbatim by the XGBoost
training pipeline (``eligibility/run_model_pipeline.py``) and the staff-portal
demo seed (``services/api/app/portal/seed.py``). See ``FEATURE_CONTRACT.md``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TypeVar

from eligibility.evaluator import evaluate_rules
from eligibility.models import BeneficiaryProfile, ProgramRule


DISTRICTS = (
    "Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad", "Multan",
    "Peshawar", "Quetta", "Kasur", "Tharparkar", "Dadu", "Rajanpur",
    "Dera Ghazi Khan", "Nowshera", "Charsadda", "Umerkot", "Badin", "Sanghar",
    "Jacobabad", "Sukkur",
)
# Sub-lists the district-gated programmes below draw on. Not real Al-Khidmat
# operational boundaries -- illustrative groupings for the synthetic demo.
FLOOD_AFFECTED = ("Dadu", "Rajanpur", "Dera Ghazi Khan", "Nowshera", "Charsadda",
                  "Jacobabad", "Sukkur", "Kasur")
WATER_STRESSED = ("Tharparkar", "Umerkot", "Badin", "Sanghar", "Dadu")

EDUCATION_LEVELS = ("none", "primary", "matric", "intermediate", "graduate")
EMPLOYMENT_STATUSES = ("unemployed", "daily_wage", "self_employed", "salaried")
MARITAL_STATUSES = ("single", "married", "widowed", "divorced")


@dataclass(frozen=True)
class SyntheticProgram:
    """A demo-only programme configuration, never a claim about real policy."""

    id: str
    name: str
    domain: str
    rules: tuple[ProgramRule, ...]


@dataclass(frozen=True)
class LabeledExample:
    """One hard-rule survivor and its synthetic verification label."""

    profile_index: int
    profile: BeneficiaryProfile
    program: SyntheticProgram
    verified: bool


def _rule(
    rule_id: str,
    field: str,
    operator: str,
    value: object,
    description: str,
) -> ProgramRule:
    return ProgramRule(
        rule_id=rule_id,
        field=field,  # type: ignore[arg-type]
        operator=operator,  # type: ignore[arg-type]
        value=value,  # type: ignore[arg-type]
        description=description,
    )


def build_synthetic_programs() -> tuple[SyntheticProgram, ...]:
    """Return the demo programme catalogue: Al-Khidmat's seven real areas of
    work, each with two-to-three illustrative sub-programmes that share a
    ``domain`` but gate on different hard rules.

    The seven domains mirror alkhidmat.org/donations/area-of-work: disaster
    management, health services, education, clean water (WASH), orphan care,
    BanoQabil, and community services. Islamic Microfinance is deliberately
    NOT here -- a loan is a debt nobody is "eligible" for without applying, so
    it lives only in the marketplace module, never in eligibility discovery.

    Sub-programmes sharing a domain matters for training: the XGBoost model
    only sees the domain one-hot plus profile features and rule slack, so two
    sub-programmes with different thresholds multiply the (profile, programme)
    pairs and the rule-slack variety the model learns from, without adding a
    new feature column. The rules and thresholds below are plausible demo
    values, not a statement of real Al-Khidmat policy.
    """

    return (
        # --- 1. Disaster Management ---------------------------------------
        SyntheticProgram(
            id="disaster-management-demo",
            name="Disaster Response Grant",
            domain="disaster_management",
            rules=(_rule("DIS-01", "district", "in", list(FLOOD_AFFECTED), "Disaster-affected district"),),
        ),
        SyntheticProgram(
            id="disaster-shelter-demo",
            name="Emergency Shelter Support",
            domain="disaster_management",
            rules=(
                _rule("DIS-SH-01", "district", "in", list(FLOOD_AFFECTED), "Disaster-affected district"),
                _rule("DIS-SH-02", "owns_home", "==", False, "No owned shelter"),
            ),
        ),
        SyntheticProgram(
            id="disaster-rehab-demo",
            name="Livelihood Rehabilitation",
            domain="disaster_management",
            rules=(
                _rule("DIS-RH-01", "district", "in", list(FLOOD_AFFECTED), "Disaster-affected district"),
                _rule("DIS-RH-02", "monthly_income", "<=", 30_000, "Income threshold"),
            ),
        ),
        # --- 2. Health Services -----------------------------------------
        SyntheticProgram(
            id="health-services-demo",
            name="Individual Patient Case Support",
            domain="health_services",
            rules=(
                _rule("HEALTH-01", "monthly_income", "<=", 40_000, "Income threshold"),
                _rule("HEALTH-02", "chronic_illness_flag", "==", True, "Chronic illness confirmed"),
            ),
        ),
        SyntheticProgram(
            id="health-thalassemia-demo",
            name="Thalassemia & Blood Disorder Care",
            domain="health_services",
            rules=(
                _rule("HEALTH-TH-01", "chronic_illness_flag", "==", True, "Chronic illness confirmed"),
                _rule("HEALTH-TH-02", "age", "<=", 25, "Paediatric / young-adult patient"),
            ),
        ),
        SyntheticProgram(
            id="health-dialysis-demo",
            name="Dialysis & Kidney Care",
            domain="health_services",
            rules=(
                _rule("HEALTH-DL-01", "chronic_illness_flag", "==", True, "Chronic illness confirmed"),
                _rule("HEALTH-DL-02", "monthly_income", "<=", 60_000, "Income threshold"),
            ),
        ),
        SyntheticProgram(
            id="health-mother-child-demo",
            name="Mother & Child Health",
            domain="health_services",
            rules=(
                _rule("HEALTH-MC-01", "monthly_income", "<=", 45_000, "Income threshold"),
                _rule("HEALTH-MC-02", "dependents", ">=", 1, "Dependent in household"),
            ),
        ),
        # --- 3. Education ----------------------------------------------
        SyntheticProgram(
            id="education-program-demo",
            name="Monthly Education Stipend",
            domain="education",
            rules=(
                _rule("EDU-01", "monthly_income", "<=", 30_000, "Income threshold"),
                _rule("EDU-02", "school_age_children", ">=", 1, "School-age child present"),
            ),
        ),
        SyntheticProgram(
            id="education-orphan-demo",
            name="Orphan Education Scholarship",
            domain="education",
            rules=(
                _rule("EDU-OR-01", "is_orphan", "==", True, "Orphan status confirmed"),
                _rule("EDU-OR-02", "school_age_children", ">=", 1, "School-age child present"),
            ),
        ),
        SyntheticProgram(
            id="education-higher-demo",
            name="Higher Education Scholarship",
            domain="education",
            rules=(
                _rule("EDU-HI-01", "education_level", "in", ["intermediate", "graduate"], "Completed intermediate or above"),
                _rule("EDU-HI-02", "monthly_income", "<=", 45_000, "Income threshold"),
            ),
        ),
        # --- 4. Clean Water / WASH ------------------------------------
        SyntheticProgram(
            id="wash-program-demo",
            name="Clean Water Access",
            domain="wash",
            rules=(_rule("WASH-01", "district", "in", list(WATER_STRESSED), "Water-stressed district"),),
        ),
        SyntheticProgram(
            id="wash-school-demo",
            name="School Water & Hygiene",
            domain="wash",
            rules=(
                _rule("WASH-SC-01", "district", "in", list(WATER_STRESSED), "Water-stressed district"),
                _rule("WASH-SC-02", "school_age_children", ">=", 1, "School-age child present"),
            ),
        ),
        SyntheticProgram(
            id="wash-household-demo",
            name="Household Water Connection",
            domain="wash",
            rules=(
                _rule("WASH-HH-01", "district", "in", list(WATER_STRESSED), "Water-stressed district"),
                _rule("WASH-HH-02", "monthly_income", "<=", 35_000, "Income threshold"),
            ),
        ),
        # --- 5. Orphan Care ------------------------------------------
        SyntheticProgram(
            id="orphan-care-demo",
            name="Orphan Care Programme",
            domain="orphan_care",
            rules=(
                _rule("ORPHAN-01", "is_orphan", "==", True, "Orphan status confirmed"),
                _rule("ORPHAN-02", "dependents", ">=", 1, "Dependent household member present"),
            ),
        ),
        SyntheticProgram(
            id="orphan-kafalat-demo",
            name="Orphan Kafalat (Monthly Sponsorship)",
            domain="orphan_care",
            rules=(
                _rule("ORPHAN-KF-01", "is_orphan", "==", True, "Orphan status confirmed"),
                _rule("ORPHAN-KF-02", "age", "<=", 18, "Minor child"),
            ),
        ),
        SyntheticProgram(
            id="orphan-widow-demo",
            name="Widowed Mother Support",
            domain="orphan_care",
            rules=(
                _rule("ORPHAN-WD-01", "marital_status", "==", "widowed", "Widowed head of household"),
                _rule("ORPHAN-WD-02", "dependents", ">=", 1, "Dependent household member present"),
            ),
        ),
        # --- 6. BanoQabil ------------------------------------------
        SyntheticProgram(
            id="bano-qabil-demo",
            name="Bano Qabil Skills Programme",
            domain="bano_qabil",
            rules=(_rule("BANO-01", "employment_status", "==", "unemployed", "Currently unemployed"),),
        ),
        SyntheticProgram(
            id="bano-qabil-it-demo",
            name="Bano Qabil IT & Digital Skills",
            domain="bano_qabil",
            rules=(
                _rule("BANO-IT-01", "age", "<=", 30, "Youth applicant"),
                _rule("BANO-IT-02", "education_level", "in", ["matric", "intermediate", "graduate"], "Matric or above"),
            ),
        ),
        SyntheticProgram(
            id="bano-qabil-vocational-demo",
            name="Bano Qabil Vocational Training",
            domain="bano_qabil",
            rules=(
                _rule("BANO-VC-01", "age", "<=", 40, "Working-age applicant"),
                _rule("BANO-VC-02", "employment_status", "in", ["unemployed", "daily_wage"], "Unemployed or daily-wage"),
            ),
        ),
        # --- 7. Community Services --------------------------------
        SyntheticProgram(
            id="community-ration-demo",
            name="Monthly Ration Support",
            domain="community_services",
            rules=(
                _rule("COMM-RT-01", "monthly_income", "<=", 25_000, "Income threshold"),
                _rule("COMM-RT-02", "household_size", ">=", 4, "Larger household"),
            ),
        ),
        SyntheticProgram(
            id="community-marriage-demo",
            name="Marriage & Jahez Assistance",
            domain="community_services",
            rules=(
                _rule("COMM-MR-01", "marital_status", "==", "single", "Unmarried applicant"),
                _rule("COMM-MR-02", "age", ">=", 18, "Adult applicant"),
                _rule("COMM-MR-03", "monthly_income", "<=", 35_000, "Income threshold"),
            ),
        ),
        SyntheticProgram(
            id="community-deceased-family-demo",
            name="Deceased-Breadwinner Family Support",
            domain="community_services",
            rules=(
                _rule("COMM-DF-01", "marital_status", "==", "widowed", "Widowed head of household"),
                _rule("COMM-DF-02", "monthly_income", "<=", 30_000, "Income threshold"),
            ),
        ),
    )


T = TypeVar("T")


def _optional(value: T, *, missing_rate: float, rng: random.Random) -> T | None:
    return None if rng.random() < missing_rate else value


_EMPLOYMENT_INCOME_BASE = {
    "unemployed": 9_000,
    "daily_wage": 21_000,
    "self_employed": 34_000,
    "salaried": 46_000,
}
_EDUCATION_INCOME_BONUS = {
    "none": 0,
    "primary": 2_500,
    "matric": 7_000,
    "intermediate": 14_000,
    "graduate": 28_000,
}


def _draw_correlated_profile(index: int, rng: random.Random) -> BeneficiaryProfile:
    """Draw one profile from a single latent 'hardship' factor so the columns
    move together the way a real caseload does -- low education tracks low
    income tracks informal work tracks more dependents and more vulnerability.
    Independent uniform draws (the previous approach) gave the model nothing
    coherent to learn.
    """

    # hardship in [0, 1], skewed toward the middle-low: most of a facilitation
    # centre's walk-ins are poor, a long tail is extremely poor.
    hardship = rng.betavariate(2.2, 3.0)

    age_years = rng.randint(18, 78)
    date_of_birth = date.today() - timedelta(days=(age_years * 365) + rng.randint(0, 364))

    # Marital status is age- and hardship-aware (widowhood rises with both).
    if age_years < 24:
        marital_status = rng.choices(("single", "married"), weights=(0.75, 0.25))[0]
    else:
        widow_p = 0.05 + 0.20 * hardship + (0.15 if age_years > 55 else 0.0)
        marital_status = rng.choices(
            ("single", "married", "widowed", "divorced"),
            weights=(0.12, 0.72 - widow_p, widow_p, 0.16),
        )[0]

    employment_status = rng.choices(
        EMPLOYMENT_STATUSES,
        weights=(
            0.10 + 0.45 * hardship,      # unemployed
            0.20 + 0.30 * hardship,      # daily_wage
            0.35 - 0.15 * hardship,      # self_employed
            0.35 - 0.30 * hardship,      # salaried
        ),
    )[0]
    education_level = rng.choices(
        EDUCATION_LEVELS,
        weights=(
            0.08 + 0.34 * hardship,      # none
            0.15 + 0.20 * hardship,      # primary
            0.30 - 0.05 * hardship,      # matric
            0.27 - 0.20 * hardship,      # intermediate
            0.20 - 0.15 * hardship,      # graduate
        ),
    )[0]

    income = (
        _EMPLOYMENT_INCOME_BASE[employment_status]
        + _EDUCATION_INCOME_BONUS[education_level]
        - 12_000 * hardship
        + rng.gauss(0, 6_000)
    )
    monthly_income = Decimal(max(2_000, round(income / 500) * 500))

    # Larger, more dependent households at higher hardship.
    household_size = min(14, max(1, round(rng.gauss(4 + 3 * hardship, 2))))
    married = marital_status in {"married", "widowed", "divorced"}
    dependent_share = min(0.9, rng.betavariate(2, 3) + 0.25 * hardship)
    dependents = min(household_size, round(household_size * dependent_share))
    if married and dependents == 0 and household_size > 1:
        dependents = 1
    school_age_children = rng.randint(0, dependents) if dependents else 0

    has_disability = rng.random() < 0.06 + 0.14 * hardship
    chronic_illness = rng.random() < 0.10 + 0.22 * hardship
    is_orphan = age_years <= 25 and rng.random() < 0.05 + 0.10 * hardship
    owns_home = rng.random() < 0.60 - 0.38 * hardship
    prior_assistance_count = min(6, int(rng.expovariate(1 / (0.6 + 1.6 * hardship))))

    return BeneficiaryProfile(
        full_name=f"Synthetic Beneficiary {index}",
        district=rng.choice(DISTRICTS),
        household_size=_optional(household_size, missing_rate=0.04, rng=rng),
        dependents=_optional(dependents, missing_rate=0.08, rng=rng),
        school_age_children=_optional(school_age_children, missing_rate=0.12, rng=rng),
        marital_status=_optional(marital_status, missing_rate=0.08, rng=rng),
        monthly_income=_optional(monthly_income, missing_rate=0.16, rng=rng),
        employment_status=_optional(employment_status, missing_rate=0.08, rng=rng),
        owns_home=_optional(owns_home, missing_rate=0.12, rng=rng),
        education_level=_optional(education_level, missing_rate=0.12, rng=rng),
        has_disability=_optional(has_disability, missing_rate=0.08, rng=rng),
        chronic_illness_flag=_optional(chronic_illness, missing_rate=0.08, rng=rng),
        prior_assistance_count=_optional(prior_assistance_count, missing_rate=0.10, rng=rng),
        date_of_birth=_optional(date_of_birth, missing_rate=0.12, rng=rng),
        is_orphan=_optional(is_orphan, missing_rate=0.12, rng=rng),
    )


def generate_synthetic_profiles(n: int, *, seed: int = 42) -> list[BeneficiaryProfile]:
    """Generate plausible, partially complete demo profiles with no real data."""

    if n <= 0:
        raise ValueError("n must be positive")

    rng = random.Random(seed)
    return [_draw_correlated_profile(index, rng) for index in range(n)]


# Base shift on the verification-confidence logit, per programme area. Positive
# where a passing profile usually does turn out to have a confirmed material
# need (disaster, water, orphan care); near zero or negative for skills
# programmes, where passing the rules says little about verified hardship.
PROGRAM_EFFECTS = {
    "disaster_management": 0.22,
    "health_services": 0.12,
    "education": 0.04,
    "wash": 0.16,
    "orphan_care": 0.18,
    "bano_qabil": -0.06,
    "community_services": 0.08,
}


def _verification_probability(
    profile: BeneficiaryProfile,
    program: SyntheticProgram,
    rng: random.Random,
) -> float:
    """Create a noisy but learnable multi-signal demo label.

    This is the synthetic stand-in for a real verification outcome: given a
    profile that already passed the hard rules, how likely is a field officer
    to confirm a genuine, unmet material need? Signals are intentionally
    stronger than the profile noise so XGBoost has real structure to fit,
    while ``generate_labeled_dataset`` still flips a fraction of labels.
    """

    signal = PROGRAM_EFFECTS[program.domain] + rng.gauss(0.0, 0.07)

    if profile.monthly_income is not None and profile.household_size not in {None, 0}:
        income_per_head = float(profile.monthly_income) / profile.household_size
        signal += max(0.0, (20_000 - income_per_head) / 20_000) * 0.45
        signal += max(0.0, (income_per_head - 45_000) / 45_000) * -0.35

    if profile.household_size is not None and profile.dependents is not None:
        earners = max(profile.household_size - profile.dependents, 1)
        dependency_ratio = profile.dependents / earners
        signal += min(dependency_ratio / 3.0, 0.28)

    if profile.school_age_children:
        signal += min(profile.school_age_children * 0.05, 0.15)

    if profile.has_disability and profile.chronic_illness_flag:
        signal += 0.30
    elif profile.has_disability or profile.chronic_illness_flag:
        signal += 0.12

    if profile.is_orphan:
        signal += 0.16
    if profile.marital_status == "widowed":
        signal += 0.14
    if profile.owns_home is False:
        signal += 0.08
    if profile.employment_status in {"unemployed", "daily_wage"}:
        signal += 0.08
    if profile.education_level in {"none", "primary"}:
        signal += 0.06

    if profile.prior_assistance_count is not None:
        signal -= min(profile.prior_assistance_count * 0.06, 0.24)

    return 1.0 / (1.0 + math.exp(-5.5 * (signal - 0.80)))


def generate_labeled_dataset(
    profiles: list[BeneficiaryProfile],
    programs: tuple[SyntheticProgram, ...],
    *,
    noise_rate: float = 0.08,
    seed: int = 42,
) -> list[LabeledExample]:
    """Label only profile/program pairs that pass every hard policy rule."""

    if not 0.0 <= noise_rate <= 1.0:
        raise ValueError("noise_rate must be between 0 and 1")

    rng = random.Random(seed)
    examples: list[LabeledExample] = []
    for profile_index, profile in enumerate(profiles):
        for program in programs:
            if evaluate_rules(profile, program.rules).status != "pass":
                continue

            verified = rng.random() < _verification_probability(profile, program, rng)
            if rng.random() < noise_rate:
                verified = not verified
            examples.append(
                LabeledExample(
                    profile_index=profile_index,
                    profile=profile,
                    program=program,
                    verified=verified,
                )
            )
    return examples
