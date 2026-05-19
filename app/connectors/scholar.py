"""Conector Google Scholar — best-effort, conservador, no autoritativo.

Estrategia:
- Si el usuario aporta una URL de perfil, intentar parsear con `scholarly`.
- Si Scholar bloquea (captchas, IP banneada), continuar y marcar la limitación
  en el reporte. NO hacer scraping agresivo, NO usar proxies.
- Todo registro importado de Scholar lleva la marca `SourceName.GOOGLE_SCHOLAR`
  y NO puede confirmar autoría por sí solo.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from app.core.logging import get_logger
from app.core.normalize import normalize_doi, normalize_title
from app.models.citation import CitationCount
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

logger = get_logger(__name__)


_SCHOLAR_USER_RE = re.compile(r"user=([\w-]+)")


def extract_scholar_user_id(url: str) -> str | None:
    m = _SCHOLAR_USER_RE.search(url or "")
    return m.group(1) if m else None


class ScholarConnector:
    """Wrapper async sobre la lib síncrona `scholarly`. Modo conservador."""

    def __init__(self) -> None:
        try:
            from scholarly import scholarly  # type: ignore
            self._scholarly = scholarly
        except ImportError:
            self._scholarly = None

    @property
    def available(self) -> bool:
        return self._scholarly is not None

    async def fetch_profile_summary(
        self, profile_url: str
    ) -> tuple[dict[str, Any] | None, list[WorkRecord]]:
        """Intenta importar un perfil. Si falla, devuelve (None, []) sin lanzar."""
        if not self.available:
            logger.warning("scholarly no instalado; saltando Scholar")
            return None, []
        user_id = extract_scholar_user_id(profile_url)
        if not user_id:
            logger.warning("No se pudo extraer user_id de %s", profile_url)
            return None, []

        loop = asyncio.get_running_loop()

        def _fetch() -> tuple[dict[str, Any] | None, list[WorkRecord]]:
            try:
                author = self._scholarly.search_author_id(user_id)
                # filled solo si lo pedimos
                filled = self._scholarly.fill(
                    author,
                    sections=["basics", "indices", "counts", "publications"],
                )
                profile = {
                    "name": filled.get("name"),
                    "affiliation": filled.get("affiliation"),
                    "scholar_id": user_id,
                    "h_index": filled.get("hindex"),
                    "i10_index": filled.get("i10index"),
                    "citedby": filled.get("citedby"),
                    "cites_per_year": filled.get("cites_per_year") or {},
                }
                works: list[WorkRecord] = []
                for pub in (filled.get("publications") or [])[:500]:  # cap defensivo
                    bib = pub.get("bib") or {}
                    title = bib.get("title")
                    if not title:
                        continue
                    year = bib.get("pub_year")
                    venue = bib.get("citation") or bib.get("venue")
                    num_citations = pub.get("num_citations") or 0
                    source = SourceRecord(
                        source=SourceName.GOOGLE_SCHOLAR,
                        endpoint="scholar.google.com",
                        raw_id=pub.get("author_pub_id"),
                        notes="Google Scholar publication entry",
                    )
                    works.append(
                        WorkRecord(
                            title=title,
                            normalized_title=normalize_title(title),
                            year=int(year) if year and str(year).isdigit() else None,
                            venue=venue,
                            type=WorkType.OTHER,
                            source_list=[source],
                            source_confidence={SourceName.GOOGLE_SCHOLAR: 0.5},
                            citation_counts_by_source=[
                                CitationCount(
                                    source=SourceName.GOOGLE_SCHOLAR,
                                    count=int(num_citations),
                                )
                            ],
                            raw_per_source={SourceName.GOOGLE_SCHOLAR: pub},
                        )
                    )
                return profile, works
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Google Scholar falló (bloqueo o error): %s. Se continúa sin Scholar.",
                    e,
                )
                return None, []

        return await loop.run_in_executor(None, _fetch)
