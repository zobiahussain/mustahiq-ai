"""Synthetic profiles, scoped programs, and noisy verification labels."""

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
    "Lahore",
    "Karachi",
    "Islamabad",
    "Rawalpindi",
    "Faisalabad",
    "Multan",
    "Peshawar",
    "Quetta",
    "Kasur",
    "Tharparkar",
)
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
    """Return one illustrative seed programme for each scoped programme area."""

    return (
        SyntheticProgram(
            id="disaster-management-demo",
            name="Disaster Management",
            domain="disaster_management",
            rules=(_rule("DIS-01", "district", "in", ["Kasur"], "Affected district"),),
        ),
        SyntheticProgram(
            id="health-services-demo",
            name="Health Services",
            domain="health_services",
            rules=(
                _rule("HEALTH-01", "monthly_income", "<=", 40_000, "Income threshold"),
                _rule("HEALTH-02", "chronic_illness_flag", "==", True, "Chronic illness confirmed"),
            ),
        ),
        SyntheticProgram(
            id="education-program-demo",
            name="Education Program",
            domain="education",
            rules=(
                _rule("EDU-01", "monthly_income", "<=", 30_000, "Income threshold"),
                _rule("EDU-02", "school_age_children", ">=", 1, "School-age child present"),
            ),
        ),
        SyntheticProgram(
            id="wash-program-demo",
            name="WASH Program",
            domain="wash",
            rules=(_rule("WASH-01", "district", "in", ["Tharparkar"], "Water-stressed district"),),
        ),
        SyntheticProgram(
            id="orphan-care-demo",
            name="Orphan Care Program",
            domain="orphan_care",
            rules=(
                _rule("ORPHAN-01", "is_orphan", "==", True, "Orphan status confirmed"),
                _rule("ORPHAN-02", "dependents", ">=", 1, "Dependent household member present"),
            ),
        ),
        SyntheticProgram(
            id="bano-qabil-demo",
            name="Bano Qabil Program",
            domain="bano_qabil",
            rules=(_rule("BANO-01", "employment_status", "==", "unemployed", "Currently unemployed"),),
        ),
        SyntheticProgram(
            id="islamic-microfinance-demo",
            name="Islamic Microfinance",
            domain="islamic_microfinance",
            rules=(
                _rule("MICRO-01", "age", ">=", 24, "Minimum applicant age"),
                _rule("MICRO-02", "age", "<=", 60, "Maximum applicant age"),
                _rule(
                    "MICRO-03",
                    "employment_status",
                    "in",
                    ["self_employed", "salaried"],
                    "Income activity present",
                ),
            ),
        ),
    )


T = TypeVar("T")


def _optional(value: T, *, missing_rate: float, rng: random.Random) -> T | None:
    return None if rng.random() < missing_rate else value


def generate_synthetic_profiles(n: int, *, seed: int = 42) -> list[BeneficiaryProfile]:
    """Generate plausible, partially complete demo profiles with no real data."""

    if n <= 0:
        raise ValueError("n must be positive")

    rng = random.Random(seed)
    profiles: list[BeneficiaryProfile] = []
    for index in range(n):
        household_size = rng.randint(1, 9)
        dependents = rng.randint(0, household_size)
        age_years = rng.randint(18, 75)
        date_of_birth = date.today() - timedelta(days=(age_years * 365) + rng.randint(0, 364))

        profiles.append(
            BeneficiaryProfile(
                full_name=f"Synthetic Beneficiary {index}",
                district=rng.choice(DISTRICTS),
                household_size=_optional(household_size, missing_rate=0.05, rng=rng),
                dependents=_optional(dependents, missing_rate=0.10, rng=rng),
                school_age_children=_optional(rng.randint(0, dependents), missing_rate=0.15, rng=rng),
                marital_status=_optional(rng.choice(MARITAL_STATUSES), missing_rate=0.10, rng=rng),
                monthly_income=_optional(Decimal(rng.randint(5_000, 90_000)), missing_rate=0.20, rng=rng),
                employment_status=_optional(rng.choice(EMPLOYMENT_STATUSES), missing_rate=0.10, rng=rng),
                owns_home=_optional(rng.random() < 0.35, missing_rate=0.15, rng=rng),
                education_level=_optional(rng.choice(EDUCATION_LEVELS), missing_rate=0.15, rng=rng),
                has_disability=_optional(rng.random() < 0.12, missing_rate=0.10, rng=rng),
                chronic_illness_flag=_optional(rng.random() < 0.20, missing_rate=0.10, rng=rng),
                prior_assistance_count=_optional(rng.randint(0, 4), missing_rate=0.10, rng=rng),
                date_of_birth=_optional(date_of_birth, missing_rate=0.25, rng=rng),
                is_orphan=_optional(rng.random() < 0.08, missing_rate=0.15, rng=rng),
            )
        )
    return profiles


PROGRAM_EFFECTS = {
    "disaster_management": 0.15,
    "health_services": 0.10,
    "education": 0.05,
    "wash": 0.08,
    "orphan_care": 0.12,
    "bano_qabil": 0.00,
    "islamic_microfinance": -0.05,
}


def _verification_probability(
    profile: BeneficiaryProfile,
    program: SyntheticProgram,
    rng: random.Random,
) -> float:
    """Create a noisy, multi-signal demo label without using real decisions."""

    signal = PROGRAM_EFFECTS[program.domain] + rng.gauss(0.0, 0.18)

    if profile.monthly_income is not None and profile.household_size not in {None, 0}:
        income_per_head = float(profile.monthly_income) / profile.household_size
        signal += max(0.0, (25_000 - income_per_head) / 25_000) * 0.30

    if profile.household_size is not None and profile.dependents is not None:
        earners = max(profile.household_size - profile.dependents, 1)
        dependency_ratio = profile.dependents / earners
        signal += min(dependency_ratio / 4.0, 0.18)

    if profile.has_disability and profile.chronic_illness_flag:
        signal += 0.24
    elif profile.has_disability or profile.chronic_illness_flag:
        signal += 0.08

    if profile.is_orphan:
        signal += 0.12
    if profile.prior_assistance_count is not None:
        signal -= min(profile.prior_assistance_count * 0.05, 0.20)

    return 1.0 / (1.0 + math.exp(-3.0 * (signal - 0.25)))


def generate_labeled_dataset(
    profiles: list[BeneficiaryProfile],
    programs: tuple[SyntheticProgram, ...],
    *,
    noise_rate: float = 0.10,
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
