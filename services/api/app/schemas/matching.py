from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ProgramMatch(BaseModel):
    program_id: UUID
    program_name: str
    score: float
    reason: str
    status: Literal["pending_review", "pooled", "dismissed", "suppressed"]
