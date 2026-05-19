"""Identidad y registro de fuentes externas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class SourceName(str, Enum):
    """Fuentes soportadas. Orden importa: refleja jerarquía de confianza."""

    ORCID = "orcid"
    CROSSREF = "crossref"
    DATACITE = "datacite"
    ARXIV = "arxiv"
    OPENALEX = "openalex"
    ZENODO = "zenodo"
    GITHUB = "github"
    GOOGLE_SCHOLAR = "google_scholar"
    USER_FILE = "user_file"

    @property
    def is_authoritative(self) -> bool:
        """Si la fuente es autoritativa para identidad de obra."""
        return self in {
            SourceName.ORCID,
            SourceName.CROSSREF,
            SourceName.DATACITE,
            SourceName.ARXIV,
        }

    @property
    def trust_rank(self) -> int:
        """Rango de confianza (menor = más confiable)."""
        order = [
            SourceName.ORCID,
            SourceName.CROSSREF,
            SourceName.DATACITE,
            SourceName.ARXIV,
            SourceName.OPENALEX,
            SourceName.ZENODO,
            SourceName.GITHUB,
            SourceName.USER_FILE,
            SourceName.GOOGLE_SCHOLAR,
        ]
        return order.index(self)


class SourceRecord(BaseModel):
    """Registro auditable de una consulta a una fuente externa."""

    source: SourceName
    queried_at: datetime = Field(default_factory=datetime.utcnow)
    endpoint: str | None = None
    query: str | None = None
    raw_id: str | None = None
    url: HttpUrl | None = None
    notes: str | None = None

    model_config = {"frozen": False, "use_enum_values": False}
