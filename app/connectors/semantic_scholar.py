"""Conector Semantic Scholar — fuente complementaria de citas.

Útil cuando OpenAlex no indexa citas que Semantic Scholar sí tiene
(frecuente en matemáticas con DOIs Crossref de revistas Springer/Elsevier).

API gratis, sin auth, con rate-limit estricto (~1 req/s recomendado).

Endpoints usados:
  GET /paper/DOI:<doi>                  → metadata del paper
  GET /paper/DOI:<doi>/citations        → lista de citantes, con autores y year

Limitaciones documentadas:
  - Devuelve HTTP 404 para muchos DOIs arXiv (10.48550/arxiv.*); SS prioriza
    DOIs Crossref de revistas indexadas.
  - El campo `authors[].name` viene serializado como LaTeX para acentos
    ("J. R. P'erez-Buend'ia"). La normalización debe quitar apóstrofes
    Unicode antes de comparar.
"""

from __future__ import annotations

from typing import Any

from app.connectors.base import BaseConnector
from app.core.logging import get_logger

logger = get_logger(__name__)


class SemanticScholarConnector(BaseConnector):
    default_base_url = "https://api.semanticscholar.org/graph/v1"

    async def fetch_paper_basic(self, doi: str) -> dict[str, Any] | None:
        try:
            return await self.get_json(
                f"{self.base_url}/paper/DOI:{doi}",
                params={"fields": "citationCount,influentialCitationCount,title,year"},
            )
        except Exception as e:  # noqa: BLE001
            logger.info("Semantic Scholar no encontró DOI %s: %s", doi, e)
            return None

    async def fetch_citations(
        self, doi: str, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """Devuelve la lista de citantes con sus autores.

        Cada item es {'citingPaper': {'title':..., 'authors':[{'name':...}], 'year':...}}.
        """
        try:
            data = await self.get_json(
                f"{self.base_url}/paper/DOI:{doi}/citations",
                params={"fields": "title,authors,year,externalIds", "limit": limit},
            )
            return data.get("data") or []
        except Exception as e:  # noqa: BLE001
            logger.info("Semantic Scholar /citations falló para %s: %s", doi, e)
            return []
