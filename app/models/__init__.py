"""Modelos Pydantic del dominio."""

from app.models.author import AuthorProfile, ExternalIdentity
from app.models.citation import CitationMetrics, CitationCount
from app.models.source import SourceRecord, SourceName
from app.models.verification import (
    ConflictRecord,
    VerificationDecision,
    VerificationStatus,
)
from app.models.work import WorkRecord, WorkType

__all__ = [
    "AuthorProfile",
    "ExternalIdentity",
    "CitationCount",
    "CitationMetrics",
    "ConflictRecord",
    "SourceName",
    "SourceRecord",
    "VerificationDecision",
    "VerificationStatus",
    "WorkRecord",
    "WorkType",
]
