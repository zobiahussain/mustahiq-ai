from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel


class DuplicateFlagResponse(BaseModel):
    id: UUID
    profile_a_id: UUID
    profile_a_name: str
    profile_b_id: UUID
    profile_b_name: str
    similarity_score: Optional[float] = None
    matched_on: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None


class DuplicateFlagReview(BaseModel):
    status: Literal["confirmed", "dismissed"]
