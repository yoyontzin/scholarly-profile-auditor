"""Conector Crossref — enriquecimiento por DOI.

API pública: https://api.crossref.org/works/<doi>
"""

from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector
from app.core.logging import get_logger
from app.core.normalize import normalize_doi, normalize_title
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

logger = get_logger(__name__)


_CR_TYPE_MAP: dict[str, WorkType] = {
    "journal-article": WorkType.JOURNAL_ARTICLE,
    "proceedings-article": WorkType.CONFERENCE_PAPER,
    "book-chapter": WorkType.BOOK_CHAPTER,
    "book": WorkType.BOOK,
    "edited-book": WorkType.EDITED_BOOK,
    "monograph": WorkType.BOOK,
    "posted-content": WorkType.PREPRINT,
    "report": WorkType.REPORT,
    "dissertation": WorkType.THESIS,
    "dataset": WorkType.DATASET,
    "software": WorkType.SOFTWARE,
}


class CrossrefConnector(BaseConnector):
    default_base_url = "https://api.crossref.org"

    async def fetch_by_doi(self, doi: str) -> dict[str, Any] | None:
        doi_norm = normalize_doi(doi)
        if not doi_norm:
            return None
        url = f"{self.base_url}/works/{doi_norm}"
        params = {"mailto": self.cfg.env.user_email}
        try:
            data = await self.get_json(url, params=params)
            return data.get("message")
        except Exception as e:  # noqa: BLE001
            logger.warning("Crossref lookup failed for %s: %s", doi, e)
            return None

    def message_to_record(self, msg: dict[str, Any]) -> WorkRecord | None:
        titles = msg.get("title") or []
        if not titles:
            return None
        title = titles[0]
        doi = normalize_doi(msg.get("DOI"))
        cr_type = (msg.get("type") or "").lower()
        wtype = _CR_TYPE_MAP.get(cr_type, WorkType.OTHER)

        # Año: issued.date-parts[0][0]
        year = None
        for key in ("issued", "published-print", "published-online", "created"):
            d = msg.get(key) or {}
            parts = d.get("date-parts") or []
            if parts and parts[0]:
                year = int(parts[0][0])
                break

        authors = []
        coauthor_orcids = []
        for a in (msg.get("author") or []):
            nm = " ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get(
                "name"
            )
            if nm:
                authors.append(nm)
            if a.get("ORCID"):
                coauthor_orcids.append(a["ORCID"].rstrip("/").split("/")[-1])

        venue = None
        ct = msg.get("container-title") or []
        if ct:
            venue = ct[0]

        source = SourceRecord(
            source=SourceName.CROSSREF,
            endpoint=f"{self.base_url}/works/{doi}",
            raw_id=doi,
            url=f"https://doi.org/{doi}" if doi else None,
            notes="Crossref /works message",
        )

        return WorkRecord(
            title=title,
            normalized_title=normalize_title(title),
            year=year,
            doi=doi,
            venue=venue,
            type=wtype,
            authors=authors,
            coauthor_orcids=coauthor_orcids,
            publisher=msg.get("publisher"),
            source_list=[source],
            source_confidence={SourceName.CROSSREF: 0.95},
            raw_per_source={SourceName.CROSSREF: msg},
        )
