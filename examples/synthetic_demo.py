"""Demo offline: construye un PipelineResult sintético y emite todos los artefactos.

Útil para validar la cadena de exports sin tocar la red.

Uso:
    python examples/synthetic_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permitir ejecutar desde la raíz del repo
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.normalize import normalize_title  # noqa: E402
from app.metrics.citations import compute_metrics, production_by_type, production_by_year  # noqa: E402
from app.metrics.coauthor import build_coauthor_network  # noqa: E402
from app.metrics.snii import build_snii_summary  # noqa: E402
from app.models.author import AuthorProfile  # noqa: E402
from app.models.citation import CitationCount  # noqa: E402
from app.models.source import SourceName, SourceRecord  # noqa: E402
from app.models.verification import VerificationDecision, VerificationStatus  # noqa: E402
from app.models.work import WorkRecord, WorkType  # noqa: E402
from app.services.exports import export_all  # noqa: E402
from app.services.pipeline import PipelineResult  # noqa: E402


def _w(title, year, status, doi=None, arxiv=None,
       sources=None, citations=None, wtype=WorkType.JOURNAL_ARTICLE,
       authors=None):
    sources = sources or [SourceName.ORCID]
    return WorkRecord(
        title=title,
        normalized_title=normalize_title(title),
        year=year, doi=doi, arxiv_id=arxiv, type=wtype,
        authors=authors or ["Rogelio Pérez-Buendía", "M. Nopal-Coello"],
        source_list=[SourceRecord(source=s, raw_id=doi or arxiv or title[:8])
                     for s in sources],
        source_confidence={s: 0.9 for s in sources},
        citation_counts_by_source=[
            CitationCount(source=s, count=c) for s, c in (citations or {}).items()
        ],
        verification=VerificationDecision(
            status=status,
            score=1.2 if status == VerificationStatus.CONFIRMED else 0.5,
            reasons=[
                "Demo sintético: status forzado.",
                "Este registro no proviene de fuentes reales.",
            ],
        ),
    )


def main():
    author = AuthorProfile(
        orcid="0000-0002-1825-0097",
        display_name="Demo Author",
        given_names="Demo",
        family_names="Author",
        affiliations=["Synthetic Institute"],
    )

    works = [
        _w("p-adic Galois representations in arithmetic geometry", 2020,
           VerificationStatus.CONFIRMED, doi="10.1/aa",
           sources=[SourceName.ORCID, SourceName.CROSSREF],
           citations={SourceName.OPENALEX: 22, SourceName.GOOGLE_SCHOLAR: 40}),
        _w("Berkovich dynamics on gene networks", 2022,
           VerificationStatus.CONFIRMED, arxiv="2201.00001",
           sources=[SourceName.ORCID, SourceName.ARXIV],
           citations={SourceName.OPENALEX: 8}),
        _w("A condensed approach to p-adic Hodge theory", 2024,
           VerificationStatus.CONFIRMED, doi="10.1/bb",
           sources=[SourceName.ORCID, SourceName.CROSSREF],
           citations={SourceName.OPENALEX: 2, SourceName.GOOGLE_SCHOLAR: 5}),
        _w("p-adic GRN simulator", 2024,
           VerificationStatus.CONFIRMED, doi="10.5281/zenodo.demo",
           wtype=WorkType.SOFTWARE,
           sources=[SourceName.DATACITE]),
        _w("Unverified manuscript only in Scholar", 2023,
           VerificationStatus.AMBIGUOUS,
           sources=[SourceName.GOOGLE_SCHOLAR],
           citations={SourceName.GOOGLE_SCHOLAR: 3}),
        _w("Paper about cosmology by someone else", 2023,
           VerificationStatus.REJECTED, doi="10.9/x",
           authors=["John Doe"],
           sources=[SourceName.OPENALEX]),
    ]

    metrics = compute_metrics(works)
    snii = build_snii_summary(works, metrics, area="fisico_matematicas")

    result = PipelineResult(
        author=author,
        works=works,
        metrics=metrics,
        snii_summary=snii,
        coauthor_network=build_coauthor_network(works, author.display_name),
        production_by_year=production_by_year(works),
        production_by_type=production_by_type(works),
        conflicts=[],
        stage_log=[
            "ORCID: 4 obras importadas (sintético).",
            "OpenAlex: 3 obras importadas (sintético).",
            "Scholar: 1 obra importada (sintético, demuestra el caso solo-Scholar).",
            "Dedupe: 6 únicos.",
            "Scoring: 4 confirmadas, 1 ambigua, 1 rechazada.",
        ],
    )

    out_dir = ROOT / "out" / "demo"
    artifacts = export_all(result, out_dir)
    print(f"\nDemo generado en: {out_dir}\n")
    for name, path in artifacts.items():
        print(f"  • {name:30s} {path}")


if __name__ == "__main__":
    main()
