"""Análisis SNII de Cita A y Cita B (Área I: Físico-Matemáticas).

Definiciones oficiales SNII / SECIHTI, área I — Físico-Matemáticas y
Ciencias de la Tierra:

  Cita A
      "Aquellas realizadas en productos de investigación firmadas por uno
       o varios autores, entre los cuales no se encuentra ninguno que sea
       autor del trabajo al que hace referencia en la cita. Es decir, se
       deben excluir las autocitas de todos los autores."

  Cita B
      "Aquellas realizadas en productos de investigación firmadas por uno
       o varios autores, entre los cuales puede encontrarse uno o varios
       autores del trabajo al que se hace referencia en la cita, pero no
       el investigador evaluado. Es decir, se deben excluir únicamente
       las autocitas del autor seleccionado."

Notación: sea W un trabajo del autor evaluado (E), con autores A(W).
Sea C un citante con autores A(C).

  Cita A  ⇔  A(C) ∩ A(W) = ∅
  Cita B  ⇔  E ∉ A(C)
  Autocita estricta  ⇔  E ∈ A(C)

Relación: Cita A ⊆ Cita B siempre. La diferencia Cita B − Cita A son las
citas hechas por coautores históricos del trabajo W cuando E no firma el
citante.

Umbrales para Matemáticas (Criterios Específicos del Área I):
  Nivel II  ≥ 20 citas
  Nivel III ≥ 40 citas

El documento del SNII no especifica explícitamente si los umbrales son
sobre A o sobre B. La práctica habitual y la lectura estricta del criterio
("excluir autocitas de todos los autores") sugieren usar Cita A para el
expediente más conservador. El módulo reporta ambas separadamente y deja
la elección al usuario.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.connectors.openalex import OpenAlexConnector
from app.core.logging import get_logger
from app.core.normalize import normalize_person_name
from app.models.work import WorkRecord

logger = get_logger(__name__)


SNII_MATH_THRESHOLDS = {
    "nivel_ii_min_citas": 20,
    "nivel_iii_min_citas": 40,
}


@dataclass
class WorkCitationAnalysis:
    """Resultado por obra. Total = Cita A + (Cita B − A) + Autocitas_estrictas."""

    work_internal_id: str
    title: str
    year: int | None
    doi: str | None
    openalex_id: str | None
    work_authors: list[str] = field(default_factory=list)

    total_citers: int = 0
    cita_A: int = 0                            # estrictamente externa
    cita_B: int = 0                            # E no firma el citante
    autocita_estricta: int = 0                 # E ∈ A(C)
    cita_por_coautor_historico: int = 0        # B − A (coautor de W cita, E no)
    autores_citantes_distintos_A: int = 0      # diversidad sobre Cita A
    top_external_citers_A: dict[str, int] = field(default_factory=dict)


@dataclass
class GlobalCitationSummary:
    total_works_analyzed: int
    works_with_citations: int

    total_cita_A: int
    total_cita_B: int
    total_autocita_estricta: int
    total_cita_coautor_historico: int

    autores_citantes_distintos_A_global: int
    top_external_citers_A: dict[str, int]

    meets_nivel_ii_by_A: bool
    meets_nivel_iii_by_A: bool
    meets_nivel_ii_by_B: bool
    meets_nivel_iii_by_B: bool

    diversity_ratio_A: float
    methodology_note: str
    source: str = "OpenAlex /works?filter=cites:<id>"

    @property
    def disclaimer(self) -> str:
        return (
            "Conteo proveniente exclusivamente de OpenAlex (citas abiertas "
            "indexadas con DOI/Crossref). En matemáticas la cobertura es "
            "incompleta porque MathSciNet, zbMATH y muchas citas vía arXiv "
            "no están indexadas en OpenAlex. El SNII NO emite dictamen "
            "automático de nivel: este reporte ayuda a documentar el "
            "expediente, no a sustituir la evaluación cualitativa del comité."
        )


def _author_set(work_data: dict | list[str]) -> set[str]:
    """Conjunto normalizado de autores. Acepta lista de strings o raw OpenAlex."""
    names: list[str] = []
    if isinstance(work_data, list):
        names = work_data
    elif isinstance(work_data, dict):
        for a in work_data.get("authorships", []):
            au = a.get("author") or {}
            nm = au.get("display_name")
            if nm:
                names.append(nm)
    return {normalize_person_name(n) for n in names if n}


def _classify_citer(
    citer: dict,
    work_author_names_norm: set[str],
    author_orcid: str,
    author_name_variants_norm: set[str],
) -> tuple[bool, bool, bool, list[str]]:
    """Para un citante C, devuelve (is_A, is_B, is_autocita_estricta, names_externos).

    Reglas:
      A ⇔ A(C) ∩ A(W) = ∅              (intersección vacía con autores del trabajo)
      B ⇔ ORCID_evaluado ∉ ORCIDs(C)   y nombre del evaluado tampoco aparece
      autocita_estricta = ¬B
    """
    cit_orcids: set[str] = set()
    cit_names_norm: list[str] = []
    cit_names_raw: list[str] = []
    for a in citer.get("authorships", []):
        au = a.get("author") or {}
        nm = au.get("display_name") or ""
        oc = au.get("orcid")
        if nm:
            cit_names_raw.append(nm)
            cit_names_norm.append(normalize_person_name(nm))
        if oc:
            cit_orcids.add(oc.rstrip("/").split("/")[-1])

    # E ∈ A(C)?
    is_evaluado_en_citante = (
        author_orcid in cit_orcids
        or bool(set(cit_names_norm) & author_name_variants_norm)
    )

    # A(C) ∩ A(W): por nombre normalizado, MÁS la regla dura "el evaluado
    # siempre es autor de W" (porque W es trabajo del evaluado). Por tanto, si
    # el evaluado firma el citante, A(C) ∩ A(W) ≠ ∅ aunque el nombre no
    # matchee A(W) por variantes (p. ej. "J. R." vs "J. Rogelio").
    overlap_with_work = (
        bool(set(cit_names_norm) & work_author_names_norm)
        or is_evaluado_en_citante
    )

    is_A = not overlap_with_work               # intersección vacía
    is_B = not is_evaluado_en_citante
    is_autocita_estricta = is_evaluado_en_citante

    # Si es cita externa (A), juntamos los nombres del citante para diversidad
    names_externos = cit_names_raw if is_A else []
    return is_A, is_B, is_autocita_estricta, names_externos


async def analyze_work_citations(
    work: WorkRecord,
    author_orcid: str,
    author_name_variants_norm: set[str],
    openalex_conn: OpenAlexConnector,
    per_page: int = 100,
    max_pages: int = 20,
) -> WorkCitationAnalysis:
    """Cuenta Cita A y Cita B de una obra del autor."""
    oa_id: str | None = None
    for s in work.source_list:
        if s.source.value == "openalex" and s.raw_id:
            oa_id = s.raw_id.split("/")[-1]
            break
    if not oa_id and work.doi:
        oa_work = await openalex_conn.fetch_work_by_doi(work.doi)
        if oa_work:
            oa_id = (oa_work.get("id") or "").split("/")[-1]

    base = WorkCitationAnalysis(
        work_internal_id=work.internal_id,
        title=work.title,
        year=work.year,
        doi=work.doi,
        openalex_id=oa_id,
        work_authors=list(work.authors),
    )

    if not oa_id:
        return base

    work_author_names_norm = {normalize_person_name(a) for a in work.authors if a}

    cursor = "*"
    page = 0
    cita_A = cita_B = autocita = 0
    citers_A_names: list[str] = []

    while page < max_pages and cursor:
        try:
            data = await openalex_conn.get_json(
                f"{openalex_conn.base_url}/works",
                params={
                    "filter": f"cites:{oa_id}",
                    "per-page": per_page,
                    "cursor": cursor,
                    "mailto": openalex_conn.cfg.env.user_email,
                },
            )
        except Exception as e:
            logger.warning("Falló fetch de citers para %s: %s", oa_id, e)
            break

        results = data.get("results") or []
        if not results:
            break

        for cit in results:
            is_A, is_B, is_auto, names_ext = _classify_citer(
                cit, work_author_names_norm, author_orcid, author_name_variants_norm
            )
            if is_A:
                cita_A += 1
                citers_A_names.extend(names_ext)
            if is_B:
                cita_B += 1
            if is_auto:
                autocita += 1

        cursor = (data.get("meta") or {}).get("next_cursor")
        page += 1

    diversity_counter = Counter(citers_A_names)
    base.total_citers = cita_B + autocita  # B incluye A; B + autocitas = total
    base.cita_A = cita_A
    base.cita_B = cita_B
    base.autocita_estricta = autocita
    base.cita_por_coautor_historico = cita_B - cita_A
    base.autores_citantes_distintos_A = len(diversity_counter)
    base.top_external_citers_A = dict(diversity_counter.most_common(10))
    return base


def aggregate_global(per_work: list[WorkCitationAnalysis]) -> GlobalCitationSummary:
    total_A = sum(w.cita_A for w in per_work)
    total_B = sum(w.cita_B for w in per_work)
    total_auto = sum(w.autocita_estricta for w in per_work)
    total_coautor = sum(w.cita_por_coautor_historico for w in per_work)

    global_A: Counter[str] = Counter()
    for w in per_work:
        for nm, n in w.top_external_citers_A.items():
            global_A[nm] += n
    distinct_A = len(global_A)
    diversity = (total_A / distinct_A) if distinct_A else 0.0
    n_with = sum(1 for w in per_work if w.total_citers > 0)

    return GlobalCitationSummary(
        total_works_analyzed=len(per_work),
        works_with_citations=n_with,
        total_cita_A=total_A,
        total_cita_B=total_B,
        total_autocita_estricta=total_auto,
        total_cita_coautor_historico=total_coautor,
        autores_citantes_distintos_A_global=distinct_A,
        top_external_citers_A=dict(global_A.most_common(20)),
        meets_nivel_ii_by_A=total_A >= SNII_MATH_THRESHOLDS["nivel_ii_min_citas"],
        meets_nivel_iii_by_A=total_A >= SNII_MATH_THRESHOLDS["nivel_iii_min_citas"],
        meets_nivel_ii_by_B=total_B >= SNII_MATH_THRESHOLDS["nivel_ii_min_citas"],
        meets_nivel_iii_by_B=total_B >= SNII_MATH_THRESHOLDS["nivel_iii_min_citas"],
        diversity_ratio_A=round(diversity, 3),
        methodology_note=(
            "Para cada obra confirmada con OpenAlex Work ID se consulta "
            "'/works?filter=cites:<id>' paginado. Cada citante C con autores "
            "A(C) se clasifica contra los autores A(W) de la obra W:\n"
            "  Cita A  ⇔  A(C) ∩ A(W) = ∅\n"
            "  Cita B  ⇔  el investigador evaluado ∉ A(C)\n"
            "  Autocita estricta  ⇔  el investigador evaluado ∈ A(C)\n"
            "Comparaciones de autores hechas por nombre normalizado (unidecode + "
            "lowercase, sin acentos ni puntuación) y por ORCID cuando OpenAlex "
            "lo expone."
        ),
    )


async def run_snii_citation_analysis(
    works: list[WorkRecord],
    author_orcid: str,
    author_name_variants: list[str],
    only_confirmed: bool = True,
) -> tuple[list[WorkCitationAnalysis], GlobalCitationSummary]:
    from app.models.verification import VerificationStatus

    pool = works
    if only_confirmed:
        pool = [
            w for w in works
            if w.verification
            and w.verification.status
            in {VerificationStatus.CONFIRMED, VerificationStatus.USER_OVERRIDE}
        ]

    variants_norm = {normalize_person_name(v) for v in author_name_variants if v}
    oa = OpenAlexConnector()
    results: list[WorkCitationAnalysis] = []
    for w in pool:
        r = await analyze_work_citations(w, author_orcid, variants_norm, oa)
        results.append(r)
        logger.info(
            "Obra '%s': A=%d  B=%d  auto=%d  B-A=%d",
            w.title[:50], r.cita_A, r.cita_B, r.autocita_estricta,
            r.cita_por_coautor_historico,
        )
    summary = aggregate_global(results)
    return results, summary
