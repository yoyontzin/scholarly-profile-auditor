"""Métricas bibliométricas por fuente.

Política central: NO sumar citas entre fuentes. Si se necesita un agregado,
se debe declarar la política de consolidación explícitamente.
"""

from __future__ import annotations

from collections import defaultdict

from app.core.logging import get_logger
from app.models.citation import CitationMetrics
from app.models.source import SourceName
from app.models.verification import VerificationStatus
from app.models.work import WorkRecord

logger = get_logger(__name__)


def h_index(citations: list[int]) -> int:
    """h tal que ≥ h trabajos tienen ≥ h citas."""
    if not citations:
        return 0
    sorted_c = sorted(citations, reverse=True)
    h = 0
    for i, c in enumerate(sorted_c, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def i10_index(citations: list[int]) -> int:
    """Número de trabajos con ≥ 10 citas."""
    return sum(1 for c in citations if c >= 10)


def compute_metrics(
    works: list[WorkRecord],
    consider_only_confirmed: bool = True,
) -> CitationMetrics:
    """Calcula métricas por fuente sobre los trabajos confirmados (por defecto)."""
    if consider_only_confirmed:
        pool = [
            w
            for w in works
            if w.verification
            and w.verification.status
            in {VerificationStatus.CONFIRMED, VerificationStatus.USER_OVERRIDE}
        ]
    else:
        pool = works

    by_source: dict[SourceName, int] = defaultdict(int)
    cites_per_source: dict[SourceName, list[int]] = defaultdict(list)
    cites_per_year: dict[SourceName, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    works_zero = 0

    for w in pool:
        has_any_count = False
        for c in w.citation_counts_by_source:
            by_source[c.source] += c.count
            cites_per_source[c.source].append(c.count)
            if w.year is not None:
                cites_per_year[c.source][w.year] += c.count
            has_any_count = True
        if not has_any_count:
            works_zero += 1

    h_by_source = {s: h_index(v) for s, v in cites_per_source.items()}
    i10_by_source = {s: i10_index(v) for s, v in cites_per_source.items()}

    # Cobertura
    total = len(pool)
    with_doi = sum(1 for w in pool if w.doi)
    with_orcid = sum(1 for w in pool if SourceName.ORCID in w.source_confidence)
    with_openalex = sum(1 for w in pool if SourceName.OPENALEX in w.source_confidence)
    only_scholar = sum(
        1
        for w in pool
        if w.source_confidence
        and set(w.source_confidence.keys()) == {SourceName.GOOGLE_SCHOLAR}
    )

    coverage = {
        "n_works_considered": float(total),
        "pct_with_doi": _pct(with_doi, total),
        "pct_with_orcid_source": _pct(with_orcid, total),
        "pct_with_openalex_source": _pct(with_openalex, total),
        "pct_only_scholar": _pct(only_scholar, total),
    }

    notes: list[str] = []
    if only_scholar > 0:
        notes.append(
            f"{only_scholar} obras solo aparecen en Google Scholar; tratar con cautela."
        )
    if SourceName.GOOGLE_SCHOLAR in by_source and SourceName.OPENALEX in by_source:
        scholar = by_source[SourceName.GOOGLE_SCHOLAR]
        openalex = by_source[SourceName.OPENALEX]
        if scholar > 0 and openalex > 0:
            ratio = scholar / openalex if openalex else float("inf")
            if ratio > 2.0:
                notes.append(
                    f"Scholar reporta {ratio:.1f}× las citas de OpenAlex; "
                    "Scholar suele incluir auto-citas, tesis y repositorios sin arbitraje."
                )

    return CitationMetrics(
        by_source=dict(by_source),
        h_index_by_source=h_by_source,
        i10_index_by_source=i10_by_source,
        citations_per_year_by_source={
            s: dict(d) for s, d in cites_per_year.items()
        },
        works_with_zero_citations=works_zero,
        coverage=coverage,
        consolidation_policy="report_per_source_only",
        notes=notes,
    )


def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 2) if den else 0.0


def production_by_year(works: list[WorkRecord]) -> dict[int, int]:
    """Conteo de obras confirmadas por año."""
    counts: dict[int, int] = defaultdict(int)
    for w in works:
        if (
            w.verification
            and w.verification.status == VerificationStatus.CONFIRMED
            and w.year is not None
        ):
            counts[w.year] += 1
    return dict(sorted(counts.items()))


def production_by_type(works: list[WorkRecord]) -> dict[str, int]:
    """Conteo por tipo entre confirmadas."""
    counts: dict[str, int] = defaultdict(int)
    for w in works:
        if w.verification and w.verification.status == VerificationStatus.CONFIRMED:
            counts[w.type.value] += 1
    return dict(counts)
