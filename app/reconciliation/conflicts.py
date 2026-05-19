"""Detección de conflictos entre fuentes para una misma obra."""

from __future__ import annotations

from rapidfuzz import fuzz

from app.core.normalize import normalize_title
from app.models.source import SourceName
from app.models.verification import ConflictRecord
from app.models.work import WorkRecord


def detect_conflicts(work: WorkRecord) -> list[ConflictRecord]:
    """Examina raw_per_source en busca de discrepancias en year, title, venue."""
    if len(work.raw_per_source) < 2:
        return []
    conflicts: list[ConflictRecord] = []

    # ---- Year ----
    years: dict[SourceName, str] = {}
    for src, raw in work.raw_per_source.items():
        y = _extract_year(src, raw)
        if y is not None:
            years[src] = str(y)
    if len({v for v in years.values()}) > 1:
        conflicts.append(
            ConflictRecord(
                work_internal_id=work.internal_id,
                field="year",
                values=years,
                severity="warn",
                notes="Distintos años reportados entre fuentes.",
            )
        )

    # ---- Title (fuzzy) ----
    titles: dict[SourceName, str] = {}
    for src, raw in work.raw_per_source.items():
        t = _extract_title(src, raw)
        if t:
            titles[src] = t
    if len(titles) >= 2:
        norm_set = {normalize_title(t) for t in titles.values()}
        if len(norm_set) > 1:
            # Verificar similitud
            arr = list(titles.values())
            min_sim = 100
            for i in range(len(arr)):
                for j in range(i + 1, len(arr)):
                    sim = fuzz.token_set_ratio(arr[i], arr[j])
                    min_sim = min(min_sim, sim)
            if min_sim < 90:
                conflicts.append(
                    ConflictRecord(
                        work_internal_id=work.internal_id,
                        field="title",
                        values=titles,
                        severity="warn" if min_sim < 70 else "info",
                        notes=f"Similitud mínima entre fuentes: {min_sim}.",
                    )
                )

    # ---- Venue ----
    venues: dict[SourceName, str] = {}
    for src, raw in work.raw_per_source.items():
        v = _extract_venue(src, raw)
        if v:
            venues[src] = v
    if len({normalize_title(v) for v in venues.values()}) > 1:
        conflicts.append(
            ConflictRecord(
                work_internal_id=work.internal_id,
                field="venue",
                values=venues,
                severity="info",
                notes="Diferentes venues reportados (abreviaturas distintas, posiblemente).",
            )
        )

    return conflicts


def _extract_year(src: SourceName, raw: dict) -> int | None:
    if src == SourceName.ORCID:
        pd = raw.get("publication-date") or {}
        y = (pd.get("year") or {}).get("value")
        return int(y) if y and str(y).isdigit() else None
    if src in (SourceName.CROSSREF, SourceName.OPENALEX):
        for key in ("issued", "published-print", "published-online"):
            d = raw.get(key) or {}
            parts = d.get("date-parts") or []
            if parts and parts[0]:
                return int(parts[0][0])
        if raw.get("publication_year"):
            return int(raw["publication_year"])
    if src == SourceName.DATACITE:
        y = raw.get("publicationYear")
        return int(y) if y and str(y).isdigit() else None
    if src == SourceName.GOOGLE_SCHOLAR:
        bib = raw.get("bib") or {}
        y = bib.get("pub_year")
        return int(y) if y and str(y).isdigit() else None
    return None


def _extract_title(src: SourceName, raw: dict) -> str | None:
    if src == SourceName.ORCID:
        return ((raw.get("title") or {}).get("title") or {}).get("value")
    if src == SourceName.CROSSREF:
        ts = raw.get("title") or []
        return ts[0] if ts else None
    if src == SourceName.OPENALEX:
        return raw.get("title") or raw.get("display_name")
    if src == SourceName.DATACITE:
        ts = raw.get("titles") or []
        return ts[0].get("title") if ts else None
    if src == SourceName.GOOGLE_SCHOLAR:
        return (raw.get("bib") or {}).get("title")
    return None


def _extract_venue(src: SourceName, raw: dict) -> str | None:
    if src == SourceName.CROSSREF:
        ct = raw.get("container-title") or []
        return ct[0] if ct else None
    if src == SourceName.OPENALEX:
        return ((raw.get("primary_location") or {}).get("source") or {}).get(
            "display_name"
        )
    if src == SourceName.ORCID:
        return (raw.get("journal-title") or {}).get("value")
    return None
