from uuid import UUID
from pydantic import BaseModel


class ProgramMatch(BaseModel):
    program_id: UUID
    program_name: str
    score: float
    reason: str
