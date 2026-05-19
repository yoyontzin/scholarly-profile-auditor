"""Métricas de citación. Política: nunca sumar entre fuentes salvo consolidación explícita."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.source import SourceName


class CitationCount(BaseModel):
    """Conteo de citas en una fuente concreta. Inmutable por diseño."""

    source: SourceName
    count: int = Field(ge=0)
    queried_at: datetime = Field(default_factory=datetime.utcnow)
    work_internal_id: str | None = None  # None = agregado del autor

    model_config = {"frozen": True}


class CitationMetrics(BaseModel):
    """Métricas agregadas por fuente. NO se cruzan fuentes ciegamente."""

    by_source: dict[SourceName, int] = Field(default_factory=dict)
    h_index_by_source: dict[SourceName, int] = Field(default_factory=dict)
    i10_index_by_source: dict[SourceName, int] = Field(default_factory=dict)
    citations_per_year_by_source: dict[SourceName, dict[int, int]] = Field(
        default_factory=dict
    )
    works_with_zero_citations: int = 0
    coverage: dict[str, float] = Field(default_factory=dict)  # % con DOI, % con ORCID, etc.

    consolidation_policy: Literal[
        "report_per_source_only", "union_by_doi", "max_per_work"
    ] = "report_per_source_only"

    notes: list[str] = Field(default_factory=list)
