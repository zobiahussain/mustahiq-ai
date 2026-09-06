"""Pure orchestration of hard rules, confidence scoring, and explanations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, field_validator, model_validator

from data.features import build_feature_row

from .evaluator import evaluate_rules
from .models import BeneficiaryProfile, ProgramRule
from .persistence import SavedScorer
from .reasoning import explain


DiscoveryDomain = Literal[
    "disaster_management",
    "health_services",
    "education",
    "wash",
    "orphan_care",
    "bano_qabil",
    "islamic_microfinance",
]
DiscoveryStatus = Literal["pending_review", "suppressed", "not_eligible", "incomplete"]
SUPPRESSION_SUFFIX = (
    " This programme requires an explicit application and will not be sent for proactive outreach."
)


class DiscoveryProgram(BaseModel):
    """The programme fields the pure discovery engine needs from an active row."""

    model_config = ConfigDict(extra="forbid", strict=True)

    program_id: StrictStr
    name: StrictStr
    domain: DiscoveryDomain
    rules: tuple[ProgramRule, ...] | list[ProgramRule] = Field(min_length=1)
    requires_explicit_application: StrictBool = False

    @field_validator("program_id", "name")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class DiscoveryResult(BaseModel):
    """One in-memory result per programme, ready for later API persistence mapping."""

    model_config = ConfigDict(extra="forbid", strict=True)

    program_id: StrictStr
    status: DiscoveryStatus
    score: float | None
    reason: StrictStr

    @field_validator("program_id", "reason")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_score_status_pair(self) -> "DiscoveryResult":
        actionable = self.status in {"pending_review", "suppressed"}
        if actionable and self.score is None:
            raise ValueError("actionable results require a confidence score")
        if not actionable and self.score is not None:
            raise ValueError("non-actionable results must not include a confidence score")
        return self


def discover_profile(
    profile: BeneficiaryProfile,
    programs: Sequence[DiscoveryProgram],
    scorer: SavedScorer,
) -> list[DiscoveryResult]:
    """Evaluate one profile against many active programmes in input order."""

    results: list[DiscoveryResult] = []
    for program in programs:
        evaluation = evaluate_rules(profile, program.rules)
        if evaluation.status != "pass":
            results.append(
                DiscoveryResult(
                    program_id=program.program_id,
                    status="not_eligible" if evaluation.status == "fail" else "incomplete",
                    score=None,
                    reason=explain(evaluation, program.rules, None),
                )
            )
            continue

        feature_row = build_feature_row(
            profile,
            program_domain=program.domain,
            program_rules=program.rules,
        )
        score = scorer.predict_confidence(feature_row)
        reason = explain(evaluation, program.rules, score)
        status: DiscoveryStatus = "pending_review"
        if program.requires_explicit_application:
            status = "suppressed"
            reason += SUPPRESSION_SUFFIX

        results.append(
            DiscoveryResult(
                program_id=program.program_id,
                status=status,
                score=score,
                reason=reason,
            )
        )
    return results
