"""Conector OpenAlex — útil para desambiguación autor-obra y métricas agregadas.

OpenAlex es gratis y sin autenticación. La "polite pool" se activa pasando
un email en el parámetro `mailto`.

Endpoints:
  /authors?filter=orcid:<orcid>
  /works?filter=author.orcid:<orcid>&per-page=200
  /works/<openalex_id>
"""

from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector
from app.core.logging import get_logger
from app.core.normalize import normalize_arxiv, normalize_doi, normalize_title
from app.models.citation import CitationCount
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

logger = get_logger(__name__)

_OA_TYPE_MAP: dict[str, WorkType] = {
    "journal-article": WorkType.JOURNAL_ARTICLE,
    "proceedings-article": WorkType.CONFERENCE_PAPER,
    "book-chapter": WorkType.BOOK_CHAPTER,
    "book": WorkType.BOOK,
    "edited-book": WorkType.EDITED_BOOK,
    "preprint": WorkType.PREPRINT,
    "posted-content": WorkType.PREPRINT,
    "report": WorkType.REPORT,
    "dissertation": WorkType.THESIS,
    "dataset": WorkType.DATASET,
    "software": WorkType.SOFTWARE,
}


class OpenAlexConnector(BaseConnector):
    default_base_url = "https://api.openalex.org"

    async def fetch_author_by_orcid(self, orcid: str) -> dict[str, Any] | None:
        params = {
            "filter": f"orcid:{orcid}",
            "mailto": self.cfg.env.user_email,
        }
        data = await self.get_json(f"{self.base_url}/authors", params=params)
        results = data.get("results") or []
        return results[0] if results else None

    async def fetch_works_by_orcid(
        self, orcid: str, per_page: int = 100, max_pages: int = 10
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor = "*"
        page = 0
        while page < max_pages:
            params = {
                "filter": f"author.orcid:{orcid}",
                "per-page": per_page,
                "cursor": cursor,
                "mailto": self.cfg.env.user_email,
            }
            data = await self.get_json(f"{self.base_url}/works", params=params)
            chunk = data.get("results") or []
            items.extend(chunk)
            meta = data.get("meta") or {}
            cursor = meta.get("next_cursor")
            page += 1
            if not cursor or not chunk:
                break
        logger.info("OpenAlex %s: %d works (pages=%d)", orcid, len(items), page)
        return items

    async def fetch_work_by_doi(self, doi: str) -> dict[str, Any] | None:
        url = f"{self.base_url}/works/doi:{doi}"
        try:
            return await self.get_json(url, params={"mailto": self.cfg.env.user_email})
        except Exception as e:  # noqa: BLE001
            logger.warning("OpenAlex DOI lookup failed for %s: %s", doi, e)
            return None

    # ------------------------------------------------------------------
    def work_to_record(self, w: dict[str, Any]) -> WorkRecord | None:
        title = w.get("title") or w.get("display_name")
        if not title:
            return None
        doi = normalize_doi(w.get("doi"))
        oa_type = (w.get("type") or "").lower()
        wtype = _OA_TYPE_MAP.get(oa_type, WorkType.OTHER)
        year = w.get("publication_year")

        # arXiv: a veces viene como locations.host_organization o como ids.arxiv
        arxiv_id = None
        for loc in (w.get("locations") or []):
            srcid = ((loc.get("source") or {}).get("display_name") or "").lower()
            if "arxiv" in srcid:
                landing = loc.get("landing_page_url") or ""
                arxiv_id = normalize_arxiv(landing)
                if arxiv_id:
                    break

        # autores
        authors: list[str] = []
        coauthor_orcids: list[str] = []
        for a in (w.get("authorships") or []):
            au = a.get("author") or {}
            nm = au.get("display_name")
            orcid = au.get("orcid")
            if nm:
                authors.append(nm)
            if orcid:
                # Normalizar a 0000-… si viene como URL
                orcid_clean = orcid.rstrip("/").split("/")[-1]
                coauthor_orcids.append(orcid_clean)

        venue = ((w.get("primary_location") or {}).get("source") or {}).get(
            "display_name"
        )
        cited_by = int(w.get("cited_by_count") or 0)
        source = SourceRecord(
            source=SourceName.OPENALEX,
            endpoint=f"{self.base_url}/works/{w.get('id', '').split('/')[-1]}",
            raw_id=w.get("id"),
            notes="OpenAlex /works item",
        )
        return WorkRecord(
            title=title,
            normalized_title=normalize_title(title),
            year=year,
            doi=doi,
            arxiv_id=arxiv_id,
            venue=venue,
            type=wtype,
            authors=authors,
            coauthor_orcids=coauthor_orcids,
            source_list=[source],
            source_confidence={SourceName.OPENALEX: 0.8},
            citation_counts_by_source=[
                CitationCount(source=SourceName.OPENALEX, count=cited_by)
            ],
            raw_per_source={SourceName.OPENALEX: w},
        )
