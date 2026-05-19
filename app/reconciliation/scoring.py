"""Scoring multi-señal de autoría.

Filosofía: ninguna señal individual confirma; la convergencia las confirma.
El score es la suma ponderada de evidencias presentes, y la decisión final
depende del score Y de una política dura sobre identificadores estables.

Señales reconocidas (claves coinciden con config.yaml scoring.weights):
  orcid_explicit        ORCID del autor aparece en la obra (en coauthor_orcids)
  doi_resolvable        la obra tiene DOI normalizado
  arxiv_resolvable      la obra tiene arXiv ID
  name_exact            algún coautor coincide exactamente con autor.display_name
  name_normalized       coincidencia tras normalizar (unidecode + lowercase)
  coauthor_known        coautor conocido (lista provista por el usuario)
  affiliation_match     afiliación de la obra ∩ afiliaciones del autor ≠ ∅
  title_in_user_file    obra presente en el archivo subido por el usuario
  second_source_confirms otra fuente distinta a la primaria también lista la obra
  venue_compatible      venue ∈ lista blanca de venues conocidos del autor
  year_window_ok        año dentro de [carrera_inicio−1, presente+1]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from rapidfuzz import fuzz

from app.core.config import get_config
from app.core.logging import get_logger
from app.core.normalize import normalize_person_name
from app.models.author import AuthorProfile
from app.models.source import SourceName
from app.models.verification import VerificationDecision, VerificationStatus
from app.models.work import WorkRecord

logger = get_logger(__name__)


@dataclass
class AuthorContext:
    """Lo que se sabe del autor en el momento del scoring."""

    profile: AuthorProfile
    known_coauthor_orcids: set[str] = field(default_factory=set)
    known_coauthor_names_norm: set[str] = field(default_factory=set)
    known_venues_norm: set[str] = field(default_factory=set)
    affiliations_norm: set[str] = field(default_factory=set)
    user_supplied_titles_norm: set[str] = field(default_factory=set)
    career_start_year: int | None = None

    @classmethod
    def build(
        cls,
        profile: AuthorProfile,
        user_supplied_works: list[WorkRecord] | None = None,
        extra_aliases: list[str] | None = None,
        extra_affiliations: list[str] | None = None,
        known_venues: list[str] | None = None,
        career_start_year: int | None = None,
    ) -> "AuthorContext":
        ctx = cls(profile=profile)
        ctx.affiliations_norm = {
            normalize_person_name(a) for a in (profile.affiliations + (extra_affiliations or []))
        } - {""}
        ctx.known_venues_norm = {normalize_person_name(v) for v in (known_venues or [])} - {""}
        ctx.user_supplied_titles_norm = (
            {w.normalized_title for w in (user_supplied_works or []) if w.normalized_title}
        )
        ctx.career_start_year = career_start_year
        # Aliases extra entran como variantes de nombre del autor
        if extra_aliases:
            profile.aliases.extend(extra_aliases)
        return ctx


def _has_name_match(work: WorkRecord, profile: AuthorProfile) -> tuple[bool, bool]:
    """Devuelve (exact, normalized) match con los autores listados en la obra."""
    if not work.authors:
        return False, False
    variants = profile.name_variants()
    norm_variants = {normalize_person_name(v) for v in variants}
    for a in work.authors:
        if a in variants:
            return True, True
        if normalize_person_name(a) in norm_variants:
            return False, True
        # fuzzy con umbral alto para nombres con tildes/iniciales
        for nv in norm_variants:
            if nv and fuzz.token_sort_ratio(normalize_person_name(a), nv) >= 92:
                return False, True
    return False, False


def score_work(
    work: WorkRecord,
    ctx: AuthorContext,
) -> VerificationDecision:
    """Calcula el score y emite VerificationDecision auditable."""
    cfg = get_config()
    weights = cfg.scoring_weights()
    thresholds = cfg.scoring_thresholds()

    signals: dict[str, float] = {}
    reasons: list[str] = []
    total = 0.0

    # ---- Señal 1: ORCID explícito en la obra ----
    if ctx.profile.orcid in work.coauthor_orcids:
        w = weights.get("orcid_explicit", 1.0)
        signals["orcid_explicit"] = w
        total += w
        reasons.append("ORCID del autor presente en metadatos de la obra.")

    # ---- Señal 2-3: DOI / arXiv resoluble ----
    if work.doi:
        w = weights.get("doi_resolvable", 0.25)
        signals["doi_resolvable"] = w
        total += w
        reasons.append(f"DOI normalizado presente: {work.doi}.")
    if work.arxiv_id:
        w = weights.get("arxiv_resolvable", 0.20)
        signals["arxiv_resolvable"] = w
        total += w
        reasons.append(f"arXiv ID presente: {work.arxiv_id}.")

    # ---- Señal 4-5: nombre ----
    exact, normalized = _has_name_match(work, ctx.profile)
    if exact:
        w = weights.get("name_exact", 0.20)
        signals["name_exact"] = w
        total += w
        reasons.append("Coincidencia exacta de nombre del autor en la lista de autores.")
    elif normalized:
        w = weights.get("name_normalized", 0.10)
        signals["name_normalized"] = w
        total += w
        reasons.append("Coincidencia de nombre tras normalización (acentos / iniciales).")

    # ---- Señal 6: coautor conocido (ORCID o nombre) ----
    if work.coauthor_orcids and (set(work.coauthor_orcids) & ctx.known_coauthor_orcids):
        w = weights.get("coauthor_known", 0.20)
        signals["coauthor_known"] = w
        total += w
        reasons.append("Al menos un coautor coincide con la lista de coautores conocidos (por ORCID).")
    else:
        # Por nombre normalizado
        norm_work_authors = {normalize_person_name(a) for a in work.authors}
        inter = norm_work_authors & ctx.known_coauthor_names_norm
        if inter:
            w = weights.get("coauthor_known", 0.20)
            signals["coauthor_known"] = w
            total += w
            reasons.append(f"Coautor(es) conocidos coinciden por nombre: {sorted(inter)}.")

    # ---- Señal 7: afiliación compatible ----
    if work.affiliations and ctx.affiliations_norm:
        norm_work_affs = {normalize_person_name(a) for a in work.affiliations}
        if norm_work_affs & ctx.affiliations_norm:
            w = weights.get("affiliation_match", 0.15)
            signals["affiliation_match"] = w
            total += w
            reasons.append("Afiliación de la obra coincide con afiliaciones del autor.")

    # ---- Señal 8: presente en archivo del usuario ----
    if work.normalized_title in ctx.user_supplied_titles_norm or work.user_supplied_flag:
        w = weights.get("title_in_user_file", 0.25)
        signals["title_in_user_file"] = w
        total += w
        reasons.append("Obra declarada en el archivo de referencias del usuario.")

    # ---- Señal 9: confirmada por una segunda fuente confiable ----
    auth_sources = {
        s.source for s in work.source_list if s.source.is_authoritative
    }
    distinct_sources = {s.source for s in work.source_list}
    if len(auth_sources) >= 2 or (
        SourceName.ORCID in distinct_sources and len(distinct_sources) >= 2
    ):
        w = weights.get("second_source_confirms", 0.15)
        signals["second_source_confirms"] = w
        total += w
        reasons.append(
            f"Obra confirmada por múltiples fuentes confiables: {sorted(s.value for s in distinct_sources)}."
        )

    # ---- Señal 10: venue compatible ----
    if work.venue and ctx.known_venues_norm:
        if normalize_person_name(work.venue) in ctx.known_venues_norm:
            w = weights.get("venue_compatible", 0.05)
            signals["venue_compatible"] = w
            total += w
            reasons.append("Venue conocido del autor.")

    # ---- Señal 11: año plausible ----
    if work.year is not None:
        upper = datetime.utcnow().year + 1
        lower = (ctx.career_start_year or 1900) - 1
        if lower <= work.year <= upper:
            w = weights.get("year_window_ok", 0.05)
            signals["year_window_ok"] = w
            total += w

    # ---- Decisión ----
    confirm_thr = thresholds["confirm_threshold"]
    ambig_thr = thresholds["ambiguous_threshold"]
    require_stable = thresholds["require_stable_id_for_confirm"]

    has_orcid_explicit = "orcid_explicit" in signals
    has_stable_id = work.has_stable_identifier()

    if has_orcid_explicit:
        # ORCID explícito en la obra es evidencia dura.
        status = VerificationStatus.CONFIRMED
        reasons.append("Decisión: ORCID explícito en la obra → confirmado.")
        requires_review = False
    elif total >= confirm_thr and (has_stable_id or not require_stable):
        # Score alto + identificador estable
        status = VerificationStatus.CONFIRMED
        reasons.append(
            f"Decisión: score {total:.2f} ≥ {confirm_thr} con identificador estable → confirmado."
        )
        requires_review = False
    elif total >= confirm_thr and require_stable and not has_stable_id:
        # Score alto pero sin DOI/arXiv/ISBN: degradar a probable
        status = VerificationStatus.PROBABLE
        reasons.append(
            f"Decisión: score {total:.2f} ≥ {confirm_thr} pero SIN identificador estable → probable (revisar)."
        )
        requires_review = True
    elif total >= ambig_thr:
        status = VerificationStatus.AMBIGUOUS
        reasons.append(
            f"Decisión: score {total:.2f} ∈ [{ambig_thr}, {confirm_thr}) → ambiguo, requiere revisión."
        )
        requires_review = True
    else:
        status = VerificationStatus.REJECTED
        reasons.append(
            f"Decisión: score {total:.2f} < {ambig_thr} → rechazado por evidencia insuficiente."
        )
        requires_review = False

    return VerificationDecision(
        status=status,
        score=round(total, 4),
        signals={k: round(v, 4) for k, v in signals.items()},
        reasons=reasons,
        decided_by="auto",
        requires_review=requires_review,
    )


def score_works(
    works: list[WorkRecord],
    ctx: AuthorContext,
) -> list[WorkRecord]:
    """Anota cada WorkRecord con su VerificationDecision. In-place."""
    for w in works:
        w.verification = score_work(w, ctx)
    return works
