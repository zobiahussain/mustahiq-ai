"""Pydantic contracts for the deterministic eligibility rule engine."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool, StrictInt, StrictStr, field_validator, model_validator


AllowedRuleField = Literal[
    "monthly_income",
    "household_size",
    "dependents",
    "school_age_children",
    "marital_status",
    "employment_status",
    "owns_home",
    "district",
    "city",
    "education_level",
    "has_disability",
    "chronic_illness_flag",
    "prior_assistance_count",
]
RuleOperator = Literal["<=", ">=", "==", "in"]
RuleValue = StrictInt | Decimal | StrictStr | StrictBool | list[StrictStr]
EvaluationStatus = Literal["pass", "fail", "incomplete"]

NUMERIC_FIELDS = {
    "monthly_income",
    "household_size",
    "dependents",
    "school_age_children",
    "prior_assistance_count",
}
BOOLEAN_FIELDS = {"owns_home", "has_disability", "chronic_illness_flag"}
CATEGORICAL_FIELDS = {
    "marital_status",
    "employment_status",
    "district",
    "city",
    "education_level",
}


class ProgramRule(BaseModel):
    """One admin-confirmed hard eligibility rule for a programme."""

    model_config = ConfigDict(extra="forbid", strict=True)

    rule_id: StrictStr
    field: AllowedRuleField
    operator: RuleOperator
    value: RuleValue
    description: StrictStr

    @field_validator("rule_id", "description")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_field_operator_and_value(self) -> "ProgramRule":
        if self.field in NUMERIC_FIELDS:
            if self.operator not in {"<=", ">=", "=="}:
                raise ValueError("numeric fields support only <=, >=, or ==")
            if isinstance(self.value, bool) or not isinstance(self.value, (int, Decimal)):
                raise ValueError("numeric fields require an integer or decimal value")
        elif self.field in BOOLEAN_FIELDS:
            if self.operator != "==":
                raise ValueError("boolean fields support only ==")
            if not isinstance(self.value, bool):
                raise ValueError("boolean fields require a boolean value")
        elif self.field in CATEGORICAL_FIELDS:
            if self.operator not in {"==", "in"}:
                raise ValueError("categorical fields support only == or in")
            if self.operator == "==" and not isinstance(self.value, str):
                raise ValueError("categorical equality rules require a string value")
            if self.operator == "in":
                if not isinstance(self.value, list) or not self.value:
                    raise ValueError("in rules require a non-empty list of strings")
        return self


class BeneficiaryProfile(BaseModel):
    """A partial, structured beneficiary profile accepted by the rule engine."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID | None = None
    full_name: StrictStr | None = None
    cnic: StrictStr | None = None
    phone: StrictStr | None = None
    household_size: StrictInt | None = None
    dependents: StrictInt | None = None
    school_age_children: StrictInt | None = None
    marital_status: StrictStr | None = None
    monthly_income: Decimal | None = None
    employment_status: StrictStr | None = None
    owns_home: StrictBool | None = None
    district: StrictStr | None = None
    city: StrictStr | None = None
    education_level: StrictStr | None = None
    has_disability: StrictBool | None = None
    chronic_illness_flag: StrictBool | None = None
    prior_assistance_count: StrictInt | None = None
    domain_attributes: dict[str, JsonValue] | None = None
    staff_notes: StrictStr | None = None
    completeness_score: Decimal | None = None
    created_by_staff_id: UUID | None = None
    consent_given: StrictBool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RuleEvaluationResult(BaseModel):
    """The deterministic outcome of evaluating every hard rule."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: EvaluationStatus
    passed_rules: list[StrictStr] = Field(default_factory=list)
    failed_rules: list[StrictStr] = Field(default_factory=list)
    missing_fields: list[StrictStr] = Field(default_factory=list)
