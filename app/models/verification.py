"""Decisión de verificación de autoría y registro de conflictos."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.source import SourceName


class VerificationStatus(str, Enum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
    USER_OVERRIDE = "user_override"


class VerificationDecision(BaseModel):
    """Decisión auditable: score, status y razones textuales."""

    status: VerificationStatus
    score: float = Field(ge=0.0, le=3.0)  # ordinal, no probabilístico
    signals: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    decided_by: str = "auto"   # "auto" | "user" | "rule:<name>"
    requires_review: bool = False


class ConflictRecord(BaseModel):
    """Conflicto detectado entre fuentes para la misma obra (DOI canónico)."""

    work_internal_id: str
    field: str                        # "year", "title", "venue", "authors", ...
    values: dict[SourceName, str]     # qué dice cada fuente
    severity: str = "info"            # "info" | "warn" | "error"
    notes: str | None = None
