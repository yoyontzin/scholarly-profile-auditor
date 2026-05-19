"""WorkRecord: la unidad canónica de obra. Trazabilidad por fuente."""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl

from app.models.citation import CitationCount
from app.models.source import SourceName, SourceRecord
from app.models.verification import VerificationDecision


class WorkType(str, Enum):
    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_PAPER = "conference_paper"
    BOOK_CHAPTER = "book_chapter"
    BOOK = "book"
    EDITED_BOOK = "edited_book"
    PREPRINT = "preprint"
    THESIS = "thesis"
    REPORT = "report"
    SOFTWARE = "software"
    DATASET = "dataset"
    OTHER = "other"


class WorkRecord(BaseModel):
    """Obra consolidada con trazabilidad de fuentes y decisión de autoría."""

    internal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    title: str
    normalized_title: str

    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    isbn: str | None = None

    venue: str | None = None
    publisher: str | None = None
    type: WorkType = WorkType.OTHER
    subtype: str | None = None

    authors: list[str] = Field(default_factory=list)         # display names
    affiliations: list[str] = Field(default_factory=list)
    coauthor_orcids: list[str] = Field(default_factory=list)

    source_list: list[SourceRecord] = Field(default_factory=list)
    source_confidence: dict[SourceName, float] = Field(default_factory=dict)

    citation_counts_by_source: list[CitationCount] = Field(default_factory=list)

    url_best: HttpUrl | None = None
    repository_links: list[HttpUrl] = Field(default_factory=list)

    software_or_publication_flag: str = "publication"  # "publication" | "software" | "dataset"
    user_supplied_flag: bool = False
    duplicate_group_id: str | None = None

    verification: VerificationDecision | None = None

    # Metadata libre por fuente, para depuración y trazabilidad.
    raw_per_source: dict[SourceName, dict] = Field(default_factory=dict)

    def has_stable_identifier(self) -> bool:
        return bool(self.doi or self.arxiv_id or self.isbn)

    def best_external_url(self) -> str | None:
        if self.url_best:
            return str(self.url_best)
        if self.doi:
            return f"https://doi.org/{self.doi}"
        if self.arxiv_id:
            return f"https://arxiv.org/abs/{self.arxiv_id}"
        return None

    def citations(self, source: SourceName) -> int | None:
        for c in self.citation_counts_by_source:
            if c.source == source:
                return c.count
        return None
