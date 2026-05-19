"""Conector DataCite — DOIs de software, datasets y preprints (Zenodo, GitHub releases).

API: https://api.datacite.org/dois/<doi>
"""

from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector
from app.core.logging import get_logger
from app.core.normalize import normalize_doi, normalize_title
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

logger = get_logger(__name__)

_DC_TYPE_MAP: dict[str, WorkType] = {
    "JournalArticle": WorkType.JOURNAL_ARTICLE,
    "ConferencePaper": WorkType.CONFERENCE_PAPER,
    "BookChapter": WorkType.BOOK_CHAPTER,
    "Book": WorkType.BOOK,
    "Preprint": WorkType.PREPRINT,
    "Report": WorkType.REPORT,
    "Dissertation": WorkType.THESIS,
    "Dataset": WorkType.DATASET,
    "Software": WorkType.SOFTWARE,
}


class DataCiteConnector(BaseConnector):
    default_base_url = "https://api.datacite.org"

    async def fetch_by_doi(self, doi: str) -> dict[str, Any] | None:
        doi_norm = normalize_doi(doi)
        if not doi_norm:
            return None
        try:
            data = await self.get_json(f"{self.base_url}/dois/{doi_norm}")
            return ((data or {}).get("data") or {}).get("attributes")
        except Exception as e:  # noqa: BLE001
            logger.warning("DataCite lookup failed for %s: %s", doi, e)
            return None

    def attributes_to_record(self, attr: dict[str, Any]) -> WorkRecord | None:
        titles = attr.get("titles") or []
        if not titles:
            return None
        title = titles[0].get("title")
        if not title:
            return None
        doi = normalize_doi(attr.get("doi"))
        types = attr.get("types") or {}
        wtype = _DC_TYPE_MAP.get(types.get("resourceTypeGeneral", ""), WorkType.OTHER)
        year = attr.get("publicationYear")

        authors = []
        for c in (attr.get("creators") or []):
            nm = c.get("name") or " ".join(
                p for p in (c.get("givenName"), c.get("familyName")) if p
            )
            if nm:
                authors.append(nm)

        soft_or_pub = "publication"
        if wtype == WorkType.SOFTWARE:
            soft_or_pub = "software"
        elif wtype == WorkType.DATASET:
            soft_or_pub = "dataset"

        # repository_links
        repo_links: list[str] = []
        for rid in (attr.get("relatedIdentifiers") or []):
            if rid.get("relationType") in ("IsSupplementTo", "IsDerivedFrom", "IsSourceOf"):
                ident = rid.get("relatedIdentifier")
                if ident and ident.startswith("http"):
                    repo_links.append(ident)
        url = attr.get("url")
        if url:
            repo_links.append(url)

        source = SourceRecord(
            source=SourceName.DATACITE,
            endpoint=f"{self.base_url}/dois/{doi}",
            raw_id=doi,
            url=f"https://doi.org/{doi}" if doi else None,
        )

        return WorkRecord(
            title=title,
            normalized_title=normalize_title(title),
            year=int(year) if year and str(year).isdigit() else None,
            doi=doi,
            type=wtype,
            authors=authors,
            publisher=attr.get("publisher"),
            source_list=[source],
            source_confidence={SourceName.DATACITE: 0.92},
            repository_links=[u for u in repo_links if u.startswith("http")],  # filtrado
            software_or_publication_flag=soft_or_pub,
            raw_per_source={SourceName.DATACITE: attr},
        )
