"""Conector arXiv — wrapper sobre la lib `arxiv` (síncrona) + ejecución asíncrona.

La API de arXiv devuelve Atom XML; usar la lib oficial evita reinventar parsers.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.core.normalize import normalize_arxiv, normalize_doi, normalize_title
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

logger = get_logger(__name__)


class ArxivConnector:
    """No usa BaseConnector porque la lib `arxiv` hace su propio HTTP."""

    def __init__(self) -> None:
        try:
            import arxiv  # type: ignore
        except ImportError:
            arxiv = None  # type: ignore
        self._arxiv = arxiv

    async def fetch_by_id(self, arxiv_id: str) -> WorkRecord | None:
        aid = normalize_arxiv(arxiv_id)
        if not aid or self._arxiv is None:
            return None

        loop = asyncio.get_running_loop()

        def _query() -> Any | None:
            try:
                search = self._arxiv.Search(id_list=[aid])
                results = list(search.results())
                return results[0] if results else None
            except Exception as e:  # noqa: BLE001
                logger.warning("arXiv lookup failed for %s: %s", aid, e)
                return None

        result = await loop.run_in_executor(None, _query)
        if not result:
            return None

        authors = [a.name for a in (result.authors or [])]
        doi = normalize_doi(getattr(result, "doi", None))
        year = result.published.year if getattr(result, "published", None) else None
        source = SourceRecord(
            source=SourceName.ARXIV,
            endpoint=f"https://arxiv.org/abs/{aid}",
            raw_id=aid,
            url=f"https://arxiv.org/abs/{aid}",
        )
        return WorkRecord(
            title=result.title or "",
            normalized_title=normalize_title(result.title or ""),
            year=year,
            doi=doi,
            arxiv_id=aid,
            venue="arXiv",
            type=WorkType.PREPRINT,
            authors=authors,
            source_list=[source],
            source_confidence={SourceName.ARXIV: 0.9},
            url_best=f"https://arxiv.org/abs/{aid}",
        )
