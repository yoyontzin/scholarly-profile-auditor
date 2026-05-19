"""Análisis SNII-style — sin dictamen automático.

Reglas duras (codificadas):
  1. NO emitir un nivel SNII automático (`emit_automatic_level: false`).
  2. Reportar citas por fuente separadamente.
  3. Si una "consolidación" se ofrece, debe ser auditable (criterio explícito).
  4. Si los parámetros oficiales del área no están cargados, decirlo.

El módulo lee `config/snii_reference_params.yaml` mediante AppConfig.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_config
from app.core.logging import get_logger
from app.models.citation import CitationMetrics
from app.models.source import SourceName
from app.models.verification import VerificationStatus
from app.models.work import WorkRecord, WorkType

logger = get_logger(__name__)


def consolidate_citations_max_per_work(works: list[WorkRecord]) -> int:
    """Una política de consolidación AUDITABLE: para cada obra confirmada,
    tomar el MÁXIMO de citas entre fuentes. Esto evita doble conteo y refleja
    el upper bound observable. NO es lo mismo que sumar Scholar+OpenAlex.
    """
    total = 0
    for w in works:
        if not (
            w.verification and w.verification.status == VerificationStatus.CONFIRMED
        ):
            continue
        counts = [c.count for c in w.citation_counts_by_source]
        if counts:
            total += max(counts)
    return total


def build_snii_summary(
    works: list[WorkRecord],
    metrics: CitationMetrics,
    area: str | None = None,
) -> dict[str, Any]:
    """Devuelve un dict listo para serializar al reporte.

    NUNCA contiene un campo "nivel" o "dictamen".
    """
    cfg = get_config()
    snii_cfg = cfg.snii_params
    defaults = snii_cfg.get("defaults", {})
    area_key = area or defaults.get("area_if_unspecified", "fisico_matematicas")
    areas_block = snii_cfg.get("areas", {})
    area_block = areas_block.get(area_key, {})

    # Conteos
    confirmed = [
        w for w in works if w.verification and w.verification.status == VerificationStatus.CONFIRMED
    ]
    ambiguous = [
        w for w in works if w.verification and w.verification.status == VerificationStatus.AMBIGUOUS
    ]
    arbitrated = [
        w
        for w in confirmed
        if w.type in {WorkType.JOURNAL_ARTICLE, WorkType.CONFERENCE_PAPER}
    ]
    chapters = [w for w in confirmed if w.type == WorkType.BOOK_CHAPTER]
    books = [
        w for w in confirmed if w.type in {WorkType.BOOK, WorkType.EDITED_BOOK}
    ]
    preprints = [w for w in confirmed if w.type == WorkType.PREPRINT]
    software = [w for w in confirmed if w.type == WorkType.SOFTWARE]
    datasets = [w for w in confirmed if w.type == WorkType.DATASET]

    # Citas por fuente
    by_source = {s.value: v for s, v in metrics.by_source.items()}
    h_by_source = {s.value: v for s, v in metrics.h_index_by_source.items()}

    # Consolidación auditable (no es la oficial, es una; se declara cuál)
    consolidated_max = consolidate_citations_max_per_work(works)

    # Advertencias y observaciones
    warnings: list[str] = []
    if not snii_cfg or not areas_block:
        warnings.append(
            "No hay parámetros de referencia SNII cargados. "
            "El reporte se limita a métricas crudas por fuente."
        )
    if SourceName.GOOGLE_SCHOLAR in metrics.by_source:
        warnings.append(
            "Las citas de Google Scholar incluyen repositorios sin arbitraje "
            "y a veces auto-citas; no son comparables 1:1 con OpenAlex/Crossref."
        )
    only_scholar_pct = metrics.coverage.get("pct_only_scholar", 0.0)
    if only_scholar_pct > 5.0:
        warnings.append(
            f"{only_scholar_pct:.1f}% de las obras provienen ÚNICAMENTE de Scholar. "
            "Considere obtener DOIs o registrarlas en ORCID."
        )

    # Parámetros del área si están cargados
    area_warnings = list(area_block.get("warnings", []))
    citation_notes = list(area_block.get("citation_notes", []))
    reference_thresholds = dict(area_block.get("reference_thresholds", {}))

    return {
        "area_used": area_key,
        "area_description": area_block.get("description", ""),
        "produced_per_type": {
            "arbitrated_articles_and_conference_papers": len(arbitrated),
            "book_chapters": len(chapters),
            "books_and_edited_books": len(books),
            "preprints": len(preprints),
            "software": len(software),
            "datasets": len(datasets),
            "ambiguous_awaiting_review": len(ambiguous),
        },
        "citations_by_source": by_source,
        "h_index_by_source": h_by_source,
        "consolidation_policies": {
            "report_per_source_only": "Recomendada. Cada fuente se reporta por separado.",
            "max_per_work": {
                "description": "Toma el máximo de citas entre fuentes para cada obra; "
                "evita doble conteo pero puede inflar respecto a fuentes arbitradas.",
                "value": consolidated_max,
            },
        },
        "coverage": metrics.coverage,
        "reference_thresholds_loaded": reference_thresholds,
        "citation_notes_for_area": citation_notes,
        "warnings": warnings + area_warnings,
        "emit_automatic_level": bool(defaults.get("emit_automatic_level", False)),
        "automatic_level": None,   # explícitamente None — política dura del proyecto
        "disclaimer": (
            "Este resumen NO emite un dictamen de nivel SNII. "
            "Es una lectura cuantitativa auditable de la producción y las "
            "citas por fuente, pensada para acompañar la evaluación cualitativa "
            "que es responsabilidad del comité revisor."
        ),
    }
