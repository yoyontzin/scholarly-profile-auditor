"""Pipeline end-to-end: ingestión → reconciliación → métricas → reportes.

Orquesta los conectores y devuelve un PipelineResult consumible por la CLI,
la API y el widget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.connectors.arxiv import ArxivConnector
from app.connectors.base import BaseConnector
from app.connectors.crossref import CrossrefConnector
from app.connectors.datacite import DataCiteConnector
from app.connectors.openalex import OpenAlexConnector
from app.connectors.orcid import OrcidConnector
from app.connectors.parsers import parse_user_file
from app.connectors.scholar import ScholarConnector
from app.core.config import get_config
from app.core.logging import get_logger
from app.metrics.citations import (
    compute_metrics,
    production_by_type,
    production_by_year,
)
from app.metrics.coauthor import build_coauthor_network
from app.metrics.snii import build_snii_summary
from app.models.author import AuthorProfile
from app.models.verification import ConflictRecord, VerificationStatus
from app.models.work import WorkRecord
from app.reconciliation.conflicts import detect_conflicts
from app.reconciliation.dedupe import deduplicate
from app.reconciliation.scoring import AuthorContext, score_works

logger = get_logger(__name__)


@dataclass
class PipelineInput:
    orcid: str
    scholar_url: str | None = None
    user_refs_path: Path | None = None
    aliases: list[str] = field(default_factory=list)
    extra_affiliations: list[str] = field(default_factory=list)
    known_coauthor_orcids: set[str] = field(default_factory=set)
    known_venues: list[str] = field(default_factory=list)
    whitelist_titles: set[str] = field(default_factory=set)
    blacklist_titles: set[str] = field(default_factory=set)
    area_snii: str | None = None
    career_start_year: int | None = None


@dataclass
class PipelineResult:
    author: AuthorProfile
    works: list[WorkRecord]
    metrics: Any
    snii_summary: dict
    coauthor_network: dict
    production_by_year: dict
    production_by_type: dict
    conflicts: list[ConflictRecord]
    stage_log: list[str] = field(default_factory=list)

    @property
    def confirmed(self) -> list[WorkRecord]:
        return [w for w in self.works if w.verification and w.verification.status == VerificationStatus.CONFIRMED]

    @property
    def ambiguous(self) -> list[WorkRecord]:
        return [w for w in self.works if w.verification and w.verification.status == VerificationStatus.AMBIGUOUS]

    @property
    def rejected(self) -> list[WorkRecord]:
        return [w for w in self.works if w.verification and w.verification.status == VerificationStatus.REJECTED]


async def run_pipeline(inp: PipelineInput) -> PipelineResult:
    cfg = get_config()
    log: list[str] = []

    # ---------- Etapa 1: ORCID (identidad + works) ----------
    orcid_conn = OrcidConnector()
    author = await orcid_conn.fetch_person(inp.orcid)
    if inp.aliases:
        author.aliases.extend(inp.aliases)
    if inp.extra_affiliations:
        author.affiliations.extend(inp.extra_affiliations)
    log.append(f"ORCID: perfil cargado ({author.display_name}, {len(author.aliases)} aliases).")

    orcid_summaries = await orcid_conn.fetch_works_summary(inp.orcid)
    works_orcid: list[WorkRecord] = []
    for s in orcid_summaries:
        r = orcid_conn.summary_to_work(s, inp.orcid)
        if r is not None:
            works_orcid.append(r)
    log.append(f"ORCID: {len(works_orcid)} obras importadas.")

    # ---------- Etapa 2: OpenAlex (works + citas) ----------
    works_oa: list[WorkRecord] = []
    try:
        oa_conn = OpenAlexConnector()
        oa_works = await oa_conn.fetch_works_by_orcid(inp.orcid)
        for w in oa_works:
            r = oa_conn.work_to_record(w)
            if r is not None:
                works_oa.append(r)
        log.append(f"OpenAlex: {len(works_oa)} obras importadas.")
    except Exception as e:  # noqa: BLE001
        log.append(f"OpenAlex falló: {e}. Se continúa sin OpenAlex.")

    # ---------- Etapa 3: archivo del usuario ----------
    works_user: list[WorkRecord] = []
    if inp.user_refs_path:
        try:
            works_user = parse_user_file(inp.user_refs_path)
            log.append(f"Archivo de usuario: {len(works_user)} entradas.")
        except Exception as e:  # noqa: BLE001
            log.append(f"Parser falló para {inp.user_refs_path}: {e}.")

    # ---------- Etapa 4: Scholar (opcional) ----------
    works_scholar: list[WorkRecord] = []
    scholar_profile_info: dict | None = None
    if inp.scholar_url and cfg.scholar_enabled():
        sc_conn = ScholarConnector()
        scholar_profile_info, works_scholar = await sc_conn.fetch_profile_summary(
            inp.scholar_url
        )
        log.append(
            f"Scholar: {len(works_scholar)} obras importadas"
            + (" (perfil cargado)" if scholar_profile_info else " (sin perfil — posible bloqueo)")
        )

    # ---------- Etapa 5: deduplicación ----------
    all_works = works_orcid + works_oa + works_user + works_scholar
    log.append(f"Total bruto: {len(all_works)} registros antes de deduplicar.")
    deduped = deduplicate(all_works)
    log.append(f"Tras dedupe: {len(deduped)} registros únicos.")

    # ---------- Etapa 6: enriquecimiento por DOI/arXiv ----------
    # Para cada obra confirmable, intentar Crossref/DataCite/arXiv si no está ya
    cr_conn = CrossrefConnector()
    dc_conn = DataCiteConnector()
    ax_conn = ArxivConnector()
    enriched_count = 0
    for w in deduped:
        if w.doi and not any(s.source.value == "crossref" for s in w.source_list):
            msg = await cr_conn.fetch_by_doi(w.doi)
            if msg:
                cr_rec = cr_conn.message_to_record(msg)
                if cr_rec:
                    _merge_enrichment(w, cr_rec)
                    enriched_count += 1
            else:
                # Probar DataCite
                attr = await dc_conn.fetch_by_doi(w.doi)
                if attr:
                    dc_rec = dc_conn.attributes_to_record(attr)
                    if dc_rec:
                        _merge_enrichment(w, dc_rec)
                        enriched_count += 1
        if w.arxiv_id and not any(s.source.value == "arxiv" for s in w.source_list):
            ax_rec = await ax_conn.fetch_by_id(w.arxiv_id)
            if ax_rec:
                _merge_enrichment(w, ax_rec)
                enriched_count += 1
    log.append(f"Enriquecimiento DOI/arXiv: {enriched_count} obras complementadas.")

    # ---------- Etapa 7: whitelist / blacklist ----------
    if inp.blacklist_titles:
        before = len(deduped)
        deduped = [w for w in deduped if w.normalized_title not in inp.blacklist_titles]
        log.append(f"Blacklist removió {before - len(deduped)} obras.")
    # whitelist no remueve, solo marca para forzar review/confirm
    # (Tratamiento detallado se aplica tras scoring.)

    # ---------- Etapa 8: scoring ----------
    known_coauthor_names_norm: set[str] = set()
    ctx = AuthorContext.build(
        profile=author,
        user_supplied_works=works_user,
        extra_aliases=inp.aliases,
        extra_affiliations=inp.extra_affiliations,
        known_venues=inp.known_venues,
        career_start_year=inp.career_start_year,
    )
    ctx.known_coauthor_orcids = set(inp.known_coauthor_orcids)
    ctx.known_coauthor_names_norm = known_coauthor_names_norm
    score_works(deduped, ctx)

    # Whitelist post-scoring: forzar a CONFIRMED con marca de user_override
    if inp.whitelist_titles:
        for w in deduped:
            if w.normalized_title in inp.whitelist_titles:
                if w.verification:
                    w.verification.status = VerificationStatus.USER_OVERRIDE
                    w.verification.reasons.append(
                        "Confirmado por whitelist provista por el usuario."
                    )
                    w.verification.decided_by = "user"

    # ---------- Etapa 9: conflictos ----------
    conflicts: list[ConflictRecord] = []
    for w in deduped:
        conflicts.extend(detect_conflicts(w))
    log.append(f"Conflictos detectados: {len(conflicts)}.")

    # ---------- Etapa 10: métricas y SNII ----------
    metrics = compute_metrics(deduped, consider_only_confirmed=True)
    snii = build_snii_summary(deduped, metrics, area=inp.area_snii)
    by_year = production_by_year(deduped)
    by_type = production_by_type(deduped)
    coauth = build_coauthor_network(deduped, author.display_name)
    log.append(
        f"Métricas: confirmadas={sum(1 for w in deduped if w.verification and w.verification.status==VerificationStatus.CONFIRMED)}, "
        f"ambiguas={sum(1 for w in deduped if w.verification and w.verification.status==VerificationStatus.AMBIGUOUS)}."
    )

    # Cerrar cliente HTTP
    await BaseConnector.close_client()

    return PipelineResult(
        author=author,
        works=deduped,
        metrics=metrics,
        snii_summary=snii,
        coauthor_network=coauth,
        production_by_year=by_year,
        production_by_type=by_type,
        conflicts=conflicts,
        stage_log=log,
    )


def _merge_enrichment(base: WorkRecord, enrich: WorkRecord) -> None:
    """Anexa una fuente de enriquecimiento sin duplicar trazabilidad."""
    base.source_list.extend(enrich.source_list)
    for s, c in enrich.source_confidence.items():
        base.source_confidence[s] = max(base.source_confidence.get(s, 0.0), c)
    base.citation_counts_by_source.extend(enrich.citation_counts_by_source)
    for s, raw in enrich.raw_per_source.items():
        base.raw_per_source.setdefault(s, raw)
    base.venue = base.venue or enrich.venue
    base.publisher = base.publisher or enrich.publisher
    if len(enrich.authors) > len(base.authors):
        base.authors = enrich.authors
    for oc in enrich.coauthor_orcids:
        if oc not in base.coauthor_orcids:
            base.coauthor_orcids.append(oc)
