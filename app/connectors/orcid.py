"""Conector ORCID — API pública v3.0.

Endpoints usados:
  GET https://pub.orcid.org/v3.0/{orcid}/person     → datos personales
  GET https://pub.orcid.org/v3.0/{orcid}/works      → lista de works
  GET https://pub.orcid.org/v3.0/{orcid}/work/{put} → detalle de un work

La API pública NO requiere credenciales para registros públicos.
"""

from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector
from app.core.logging import get_logger
from app.core.normalize import normalize_arxiv, normalize_doi, normalize_title
from app.models.author import AuthorProfile, ExternalIdentity
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

logger = get_logger(__name__)


_TYPE_MAP: dict[str, WorkType] = {
    "JOURNAL_ARTICLE": WorkType.JOURNAL_ARTICLE,
    "CONFERENCE_PAPER": WorkType.CONFERENCE_PAPER,
    "BOOK_CHAPTER": WorkType.BOOK_CHAPTER,
    "BOOK": WorkType.BOOK,
    "EDITED_BOOK": WorkType.EDITED_BOOK,
    "PREPRINT": WorkType.PREPRINT,
    "WORKING_PAPER": WorkType.PREPRINT,
    "REPORT": WorkType.REPORT,
    "DISSERTATION": WorkType.THESIS,
    "SOFTWARE": WorkType.SOFTWARE,
    "DATA_SET": WorkType.DATASET,
}


class OrcidConnector(BaseConnector):
    default_base_url = "https://pub.orcid.org/v3.0"

    async def fetch_person(self, orcid: str) -> AuthorProfile:
        url = f"{self.base_url}/{orcid}/person"
        headers = {"Accept": "application/json"}
        data = await self.get_json(url, headers=headers)
        name = data.get("name") or {}
        given = (name.get("given-names") or {}).get("value")
        family = (name.get("family-name") or {}).get("value")
        credit = (name.get("credit-name") or {}).get("value")
        display = credit or " ".join(p for p in (given, family) if p)

        # Otros nombres / aliases
        aliases: list[str] = []
        for entry in ((data.get("other-names") or {}).get("other-name") or []):
            v = entry.get("content")
            if v:
                aliases.append(v)

        # Identidades externas
        identities: list[ExternalIdentity] = [
            ExternalIdentity(
                source=SourceName.ORCID.value,
                external_id=orcid,
                url=f"https://orcid.org/{orcid}",
                display_name=display,
            )
        ]
        for ext in ((data.get("external-identifiers") or {}).get("external-identifier") or []):
            t = (ext.get("external-id-type") or "").lower()
            v = ext.get("external-id-value")
            u = (ext.get("external-id-url") or {}).get("value")
            if v:
                identities.append(
                    ExternalIdentity(source=t or "external", external_id=v, url=u)
                )

        # Biografía y afiliaciones (live solo en /person + /employments si quisiéramos más)
        biography = (data.get("biography") or {}).get("content")

        return AuthorProfile(
            orcid=orcid,
            display_name=display or orcid,
            given_names=given,
            family_names=family,
            aliases=aliases,
            identities=identities,
            biography=biography,
        )

    async def fetch_works_summary(self, orcid: str) -> list[dict[str, Any]]:
        """Lista resumida de works: cada item tiene put-code y resumen mínimo."""
        url = f"{self.base_url}/{orcid}/works"
        data = await self.get_json(url, headers={"Accept": "application/json"})
        groups = data.get("group") or []
        # Cada "group" es una agrupación por external-id; tomamos el primer summary
        summaries: list[dict[str, Any]] = []
        for g in groups:
            ws = g.get("work-summary") or []
            if ws:
                summaries.append(ws[0])
        logger.info("ORCID %s: %d work-summaries", orcid, len(summaries))
        return summaries

    # ------------------------------------------------------------------
    # Conversión a WorkRecord
    # ------------------------------------------------------------------
    def summary_to_work(self, summary: dict[str, Any], orcid: str) -> WorkRecord | None:
        """Convierte un work-summary de ORCID a WorkRecord canónico."""
        title = ((summary.get("title") or {}).get("title") or {}).get("value")
        if not title:
            return None
        year = None
        pubdate = summary.get("publication-date") or {}
        y = (pubdate.get("year") or {}).get("value")
        if y and str(y).isdigit():
            year = int(y)

        # External IDs (DOI, arXiv, ISBN, etc.)
        doi: str | None = None
        arxiv: str | None = None
        isbn: str | None = None
        for eid in ((summary.get("external-ids") or {}).get("external-id") or []):
            t = (eid.get("external-id-type") or "").lower()
            v = (eid.get("external-id-value") or "")
            if t == "doi" and not doi:
                doi = normalize_doi(v)
            elif t == "arxiv" and not arxiv:
                arxiv = normalize_arxiv(v)
            elif t == "isbn" and not isbn:
                isbn = v

        wtype = _TYPE_MAP.get((summary.get("type") or "").upper(), WorkType.OTHER)
        venue = (summary.get("journal-title") or {}).get("value")
        url_best = ((summary.get("url") or {}) or {}).get("value")

        soft_or_pub = "publication"
        if wtype == WorkType.SOFTWARE:
            soft_or_pub = "software"
        elif wtype == WorkType.DATASET:
            soft_or_pub = "dataset"

        source = SourceRecord(
            source=SourceName.ORCID,
            endpoint=f"{self.base_url}/{orcid}/works",
            raw_id=str(summary.get("put-code") or ""),
            url=f"https://orcid.org/{orcid}",
            notes="ORCID work-summary",
        )

        return WorkRecord(
            title=title,
            normalized_title=normalize_title(title),
            year=year,
            doi=doi,
            arxiv_id=arxiv,
            isbn=isbn,
            venue=venue,
            type=wtype,
            source_list=[source],
            source_confidence={SourceName.ORCID: 1.0},
            url_best=url_best if url_best else None,
            software_or_publication_flag=soft_or_pub,
            raw_per_source={SourceName.ORCID: summary},
        )
