"""Deduplicación de WorkRecord.

Estrategia jerárquica:
  1. Grupos por DOI normalizado (clave fuerte).
  2. Grupos por arXiv ID normalizado.
  3. Grupos por (título_normalizado, año±1) con rapidfuzz token_set_ratio.

Cuando dos registros caen en el mismo grupo, se fusionan en uno solo:
  - el "best" hereda el internal_id del que tenga la fuente más confiable
    (trust_rank menor),
  - source_list se concatena,
  - citation_counts_by_source se concatenan (NUNCA se suman),
  - source_confidence se actualiza con el MAX por fuente,
  - raw_per_source se acumula por clave de fuente.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from rapidfuzz import fuzz

from app.core.config import get_config
from app.core.logging import get_logger
from app.core.normalize import normalize_doi
from app.models.source import SourceName
from app.models.work import WorkRecord

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Merge helper
# ---------------------------------------------------------------------------
def merge_records(records: list[WorkRecord]) -> WorkRecord:
    """Fusiona registros que ya sabemos son la misma obra.

    Preserva trazabilidad completa. El representante canónico es el de mayor
    confianza (menor trust_rank de su fuente principal).
    """
    if len(records) == 1:
        return records[0]

    # Ordenar por confianza: fuente más confiable primero
    def _confidence_key(r: WorkRecord) -> tuple[int, float]:
        if not r.source_list:
            return (999, 0.0)
        primary = min(r.source_list, key=lambda s: s.source.trust_rank)
        max_conf = max(r.source_confidence.values()) if r.source_confidence else 0.0
        return (primary.source.trust_rank, -max_conf)

    sorted_recs = sorted(records, key=_confidence_key)
    base = sorted_recs[0].model_copy(deep=True)

    # Acumular el resto
    seen_sources_in_list: set[tuple[SourceName, str | None]] = {
        (s.source, s.raw_id) for s in base.source_list
    }

    for r in sorted_recs[1:]:
        # Source records
        for s in r.source_list:
            key = (s.source, s.raw_id)
            if key not in seen_sources_in_list:
                base.source_list.append(s)
                seen_sources_in_list.add(key)
        # Confianza por fuente: MAX
        for src, conf in r.source_confidence.items():
            base.source_confidence[src] = max(
                base.source_confidence.get(src, 0.0), conf
            )
        # Citations: nunca sumar, agregar entradas
        base.citation_counts_by_source.extend(r.citation_counts_by_source)
        # Raw por fuente
        for src, raw in r.raw_per_source.items():
            base.raw_per_source.setdefault(src, raw)
        # Campos completables
        base.doi = base.doi or r.doi
        base.arxiv_id = base.arxiv_id or r.arxiv_id
        base.isbn = base.isbn or r.isbn
        base.year = base.year or r.year
        base.venue = base.venue or r.venue
        base.publisher = base.publisher or r.publisher
        # Authors: tomar la lista más larga (suele ser la más completa)
        if len(r.authors) > len(base.authors):
            base.authors = r.authors
        # Coautores ORCIDs: unión
        for oc in r.coauthor_orcids:
            if oc not in base.coauthor_orcids:
                base.coauthor_orcids.append(oc)
        # Repository links: unión
        for rl in r.repository_links:
            if rl not in base.repository_links:
                base.repository_links.append(rl)
        # User-supplied flag: OR lógico
        base.user_supplied_flag = base.user_supplied_flag or r.user_supplied_flag

    base.duplicate_group_id = base.duplicate_group_id or str(uuid.uuid4())
    return base


# ---------------------------------------------------------------------------
# Dedupe pipeline
# ---------------------------------------------------------------------------
def deduplicate(records: list[WorkRecord]) -> list[WorkRecord]:
    """Aplica las tres pasadas y devuelve la lista deduplicada."""
    if not records:
        return []
    cfg = get_config()
    params = cfg.dedupe_params()
    title_thr = int(params.get("title_similarity_threshold", 92))
    year_tol = int(params.get("year_tolerance", 1))

    # ---- Pasada 1: DOI ----
    by_doi: dict[str, list[WorkRecord]] = defaultdict(list)
    no_doi: list[WorkRecord] = []
    for r in records:
        d = normalize_doi(r.doi)
        if d:
            by_doi[d].append(r)
        else:
            no_doi.append(r)
    merged_doi = [merge_records(grp) for grp in by_doi.values()]
    logger.info("Dedupe pasada 1 (DOI): %d grupos", len(merged_doi))

    # ---- Pasada 2: arXiv ----
    by_arxiv: dict[str, list[WorkRecord]] = defaultdict(list)
    no_arxiv: list[WorkRecord] = []
    for r in no_doi:
        if r.arxiv_id:
            by_arxiv[r.arxiv_id].append(r)
        else:
            no_arxiv.append(r)
    merged_arxiv = [merge_records(grp) for grp in by_arxiv.values()]
    logger.info("Dedupe pasada 2 (arXiv): %d grupos", len(merged_arxiv))

    # ---- Pasada 3: título normalizado + año (fuzzy) ----
    # Comparación O(n^2) acotada por buckets de año (±year_tol).
    candidates = merged_doi + merged_arxiv + no_arxiv
    by_year_bucket: dict[int | None, list[WorkRecord]] = defaultdict(list)
    for r in candidates:
        by_year_bucket[r.year].append(r)

    # Agrupar fuzzy: cada registro queda en un cluster
    clusters: list[list[WorkRecord]] = []
    visited: set[str] = set()
    for r in candidates:
        if r.internal_id in visited:
            continue
        cluster = [r]
        visited.add(r.internal_id)
        # candidatos vecinos: mismo año ±tol
        year_neighbors: list[WorkRecord] = []
        if r.year is not None:
            for delta in range(-year_tol, year_tol + 1):
                year_neighbors.extend(by_year_bucket.get(r.year + delta, []))
        else:
            year_neighbors.extend(by_year_bucket.get(None, []))
        for other in year_neighbors:
            if other.internal_id in visited or other.internal_id == r.internal_id:
                continue
            # Si ambos tienen DOI distintos, NUNCA fusionarlos (palabra-clave dura)
            if r.doi and other.doi and r.doi != other.doi:
                continue
            if r.arxiv_id and other.arxiv_id and r.arxiv_id != other.arxiv_id:
                continue
            score = fuzz.token_set_ratio(r.normalized_title, other.normalized_title)
            if score >= title_thr:
                cluster.append(other)
                visited.add(other.internal_id)
        clusters.append(cluster)

    final: list[WorkRecord] = [merge_records(c) for c in clusters]
    logger.info(
        "Dedupe final: %d → %d registros únicos", len(records), len(final)
    )
    return final
