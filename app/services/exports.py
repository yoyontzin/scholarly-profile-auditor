"""Exports: JSON, BibTeX, audit_log.md, widget/data.json, report.html."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.logging import get_logger
from app.models.source import SourceName
from app.models.verification import VerificationStatus
from app.models.work import WorkRecord
from app.services.pipeline import PipelineResult

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# JSON canónico
# ---------------------------------------------------------------------------
def _work_to_json(w: WorkRecord) -> dict[str, Any]:
    return {
        "internal_id": w.internal_id,
        "title": w.title,
        "year": w.year,
        "doi": w.doi,
        "arxiv_id": w.arxiv_id,
        "isbn": w.isbn,
        "venue": w.venue,
        "publisher": w.publisher,
        "type": w.type.value,
        "authors": w.authors,
        "coauthor_orcids": w.coauthor_orcids,
        "sources": [s.source.value for s in w.source_list],
        "source_confidence": {s.value: c for s, c in w.source_confidence.items()},
        "citations_by_source": [
            {"source": c.source.value, "count": c.count, "queried_at": c.queried_at.isoformat()}
            for c in w.citation_counts_by_source
        ],
        "url_best": w.best_external_url(),
        "verification": {
            "status": w.verification.status.value if w.verification else None,
            "score": w.verification.score if w.verification else None,
            "signals": w.verification.signals if w.verification else {},
            "reasons": w.verification.reasons if w.verification else [],
            "requires_review": w.verification.requires_review if w.verification else False,
        },
        "user_supplied": w.user_supplied_flag,
    }


def export_canonical_json(result: PipelineResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "canonical_works.json"
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "author": result.author.model_dump(),
        "works": [_work_to_json(w) for w in result.works],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def export_report_json(result: PipelineResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "author": result.author.model_dump(),
        "metrics": {
            "by_source": {s.value: v for s, v in result.metrics.by_source.items()},
            "h_index_by_source": {s.value: v for s, v in result.metrics.h_index_by_source.items()},
            "i10_by_source": {s.value: v for s, v in result.metrics.i10_index_by_source.items()},
            "citations_per_year_by_source": {
                s.value: d for s, d in result.metrics.citations_per_year_by_source.items()
            },
            "coverage": result.metrics.coverage,
            "notes": result.metrics.notes,
            "consolidation_policy": result.metrics.consolidation_policy,
        },
        "snii_summary": result.snii_summary,
        "production_by_year": result.production_by_year,
        "production_by_type": result.production_by_type,
        "coauthor_network": result.coauthor_network,
        "counts": {
            "confirmed": len(result.confirmed),
            "ambiguous": len(result.ambiguous),
            "rejected": len(result.rejected),
            "conflicts": len(result.conflicts),
        },
        "conflicts": [c.model_dump() for c in result.conflicts],
        "stage_log": result.stage_log,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# BibTeX canónico
# ---------------------------------------------------------------------------
_BIB_TYPE = {
    "journal_article": "article",
    "conference_paper": "inproceedings",
    "book_chapter": "incollection",
    "book": "book",
    "edited_book": "book",
    "preprint": "unpublished",
    "thesis": "phdthesis",
    "report": "techreport",
    "software": "misc",
    "dataset": "misc",
    "other": "misc",
}


def _bib_key(w: WorkRecord, used: set[str]) -> str:
    first_author = (w.authors[0].split()[-1] if w.authors else "anon").lower()
    first_author = "".join(c for c in first_author if c.isalpha()) or "anon"
    year = w.year or "nodate"
    first_title_word = (w.normalized_title.split() + ["x"])[0]
    base = f"{first_author}{year}{first_title_word[:8]}"
    key = base
    n = 1
    while key in used:
        key = f"{base}{chr(96 + n)}"  # a, b, c, ...
        n += 1
    used.add(key)
    return key


def _escape_bib(s: str | None) -> str:
    if s is None:
        return ""
    return s.replace("{", "\\{").replace("}", "\\}")


def export_bibtex(result: PipelineResult, out_dir: Path, only_confirmed: bool = True) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "canonical_works.bib"
    used: set[str] = set()
    lines: list[str] = [
        f"% Generado por scholarly-profile-auditor el {datetime.utcnow().isoformat()}Z",
        f"% ORCID: {result.author.orcid}  Autor: {result.author.display_name}",
        f"% Solo confirmados = {only_confirmed}.",
        "",
    ]
    pool = result.confirmed if only_confirmed else result.works
    for w in pool:
        btype = _BIB_TYPE.get(w.type.value, "misc")
        key = _bib_key(w, used)
        fields = []
        fields.append(f"  title = {{{_escape_bib(w.title)}}}")
        if w.authors:
            fields.append(f"  author = {{{' and '.join(_escape_bib(a) for a in w.authors)}}}")
        if w.year:
            fields.append(f"  year = {{{w.year}}}")
        if w.venue:
            fields.append(f"  journal = {{{_escape_bib(w.venue)}}}")
        if w.doi:
            fields.append(f"  doi = {{{w.doi}}}")
        if w.arxiv_id:
            fields.append(f"  eprint = {{{w.arxiv_id}}}")
            fields.append("  archiveprefix = {arXiv}")
        if w.publisher:
            fields.append(f"  publisher = {{{_escape_bib(w.publisher)}}}")
        url = w.best_external_url()
        if url:
            fields.append(f"  url = {{{url}}}")
        lines.append(f"@{btype}{{{key},")
        lines.append(",\n".join(fields))
        lines.append("}\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# audit_log.md
# ---------------------------------------------------------------------------
def export_audit_log(result: PipelineResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "audit_log.md"
    lines: list[str] = []
    lines.append(f"# Audit log — {result.author.display_name}")
    lines.append(f"_ORCID: `{result.author.orcid}` · generado: {datetime.utcnow().isoformat()}Z_\n")
    lines.append("## Bitácora de etapas\n")
    for entry in result.stage_log:
        lines.append(f"- {entry}")
    lines.append("\n## Decisiones por obra\n")
    for w in result.works:
        if not w.verification:
            continue
        sources = ", ".join(sorted({s.source.value for s in w.source_list}))
        lines.append(f"### `{w.verification.status.value.upper()}` — {w.title}")
        lines.append(f"- Año: {w.year} · DOI: `{w.doi or '—'}` · arXiv: `{w.arxiv_id or '—'}`")
        lines.append(f"- Fuentes: {sources}")
        lines.append(f"- Score: {w.verification.score:.3f}")
        for reason in w.verification.reasons:
            lines.append(f"  - {reason}")
        if w.verification.requires_review:
            lines.append("  - **⚠ Requiere revisión manual.**")
        lines.append("")
    if result.conflicts:
        lines.append("## Conflictos entre fuentes\n")
        for c in result.conflicts:
            lines.append(f"- `[{c.severity}]` `{c.field}` — {c.notes}")
            for src, val in c.values.items():
                lines.append(f"  - `{src.value}` → {val}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# widget/data.json
# ---------------------------------------------------------------------------
def export_widget_data(result: PipelineResult, out_dir: Path) -> Path:
    widget_dir = out_dir / "widget"
    widget_dir.mkdir(parents=True, exist_ok=True)
    path = widget_dir / "data.json"
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "author": {
            "orcid": result.author.orcid,
            "display_name": result.author.display_name,
            "affiliations": result.author.affiliations,
            "aliases": result.author.aliases,
        },
        "counts": {
            "total": len(result.works),
            "confirmed": len(result.confirmed),
            "ambiguous": len(result.ambiguous),
            "rejected": len(result.rejected),
        },
        "metrics": {
            "by_source": {s.value: v for s, v in result.metrics.by_source.items()},
            "h_index_by_source": {s.value: v for s, v in result.metrics.h_index_by_source.items()},
            "coverage": result.metrics.coverage,
            "notes": result.metrics.notes,
        },
        "production_by_year": result.production_by_year,
        "production_by_type": result.production_by_type,
        "snii_summary": result.snii_summary,
        "confirmed_works": [_work_to_json(w) for w in result.confirmed],
        "ambiguous_works": [_work_to_json(w) for w in result.ambiguous],
        "rejected_works": [_work_to_json(w) for w in result.rejected],
        "conflicts": [c.model_dump() for c in result.conflicts],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# report.html
# ---------------------------------------------------------------------------
def export_report_html(result: PipelineResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tpl_dir = Path(__file__).resolve().parents[1] / "templates"
    env = Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("report.html.j2")
    rendered = tpl.render(
        author=result.author,
        works=result.works,
        confirmed=result.confirmed,
        ambiguous=result.ambiguous,
        rejected=result.rejected,
        metrics=result.metrics,
        snii=result.snii_summary,
        production_by_year=result.production_by_year,
        production_by_type=result.production_by_type,
        conflicts=result.conflicts,
        stage_log=result.stage_log,
        SourceName=SourceName,
        VerificationStatus=VerificationStatus,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )
    path = out_dir / "report.html"
    path.write_text(rendered, encoding="utf-8")
    return path


def export_all(result: PipelineResult, out_dir: Path) -> dict[str, Path]:
    """Genera todos los entregables."""
    return {
        "canonical_works.json": export_canonical_json(result, out_dir),
        "canonical_works.bib": export_bibtex(result, out_dir),
        "report.json": export_report_json(result, out_dir),
        "report.html": export_report_html(result, out_dir),
        "audit_log.md": export_audit_log(result, out_dir),
        "widget/data.json": export_widget_data(result, out_dir),
    }
