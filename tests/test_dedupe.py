"""Tests de deduplicación."""

import pytest

from app.core.normalize import normalize_title
from app.models.citation import CitationCount
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType
from app.reconciliation.dedupe import deduplicate, merge_records


def _w(title, year=2024, doi=None, arxiv=None, src=SourceName.OPENALEX, conf=0.8, cites=None):
    sources = [SourceRecord(source=src, raw_id=doi or arxiv or title[:8])]
    cc = [CitationCount(source=src, count=cites)] if cites is not None else []
    return WorkRecord(
        title=title,
        normalized_title=normalize_title(title),
        year=year,
        doi=doi,
        arxiv_id=arxiv,
        type=WorkType.JOURNAL_ARTICLE,
        source_list=sources,
        source_confidence={src: conf},
        citation_counts_by_source=cc,
        raw_per_source={src: {}},
    )


class TestDedupeByDoi:
    def test_same_doi_merges(self):
        r1 = _w("A paper", doi="10.1/a", src=SourceName.ORCID, conf=1.0)
        r2 = _w("A paper but different title", doi="10.1/a", src=SourceName.CROSSREF, conf=0.95)
        out = deduplicate([r1, r2])
        assert len(out) == 1
        # Acumula fuentes
        sources = {s.source for s in out[0].source_list}
        assert SourceName.ORCID in sources
        assert SourceName.CROSSREF in sources

    def test_different_dois_never_merge(self):
        """Regla dura: dos DOIs distintos jamás se fusionan, aunque el título sea idéntico."""
        r1 = _w("Identical title", doi="10.1/a")
        r2 = _w("Identical title", doi="10.2/b")
        out = deduplicate([r1, r2])
        assert len(out) == 2


class TestDedupeByArxiv:
    def test_same_arxiv_merges(self):
        r1 = _w("Preprint title", arxiv="2401.12345", src=SourceName.ARXIV, conf=0.9)
        r2 = _w("Preprint title with arxiv", arxiv="2401.12345", src=SourceName.OPENALEX, conf=0.8)
        out = deduplicate([r1, r2])
        assert len(out) == 1


class TestDedupeByTitleYear:
    def test_fuzzy_title_same_year_merges(self):
        r1 = _w("p-adic Galois representations", year=2024)
        r2 = _w("p-adic galois representations: a review", year=2024)
        out = deduplicate([r1, r2])
        # token_set_ratio: el subconjunto coincide perfectamente → debe fusionar
        assert len(out) == 1

    def test_different_years_outside_tolerance_dont_merge(self):
        r1 = _w("Same exact title", year=2020)
        r2 = _w("Same exact title", year=2024)
        out = deduplicate([r1, r2])
        assert len(out) == 2

    def test_different_titles_dont_merge(self):
        r1 = _w("Quantum entanglement experiment", year=2024)
        r2 = _w("p-adic motivic cohomology", year=2024)
        out = deduplicate([r1, r2])
        assert len(out) == 2


class TestMergeRecords:
    def test_citations_concatenated_not_summed(self):
        """Política central: NUNCA sumar citas entre fuentes."""
        r1 = _w("X", doi="10.1/x", src=SourceName.OPENALEX, cites=10)
        r2 = _w("X", doi="10.1/x", src=SourceName.GOOGLE_SCHOLAR, cites=30)
        merged = merge_records([r1, r2])
        # Dos entradas separadas, no una con count=40
        counts = [c.count for c in merged.citation_counts_by_source]
        assert sorted(counts) == [10, 30]
        sources = {c.source for c in merged.citation_counts_by_source}
        assert sources == {SourceName.OPENALEX, SourceName.GOOGLE_SCHOLAR}

    def test_canonical_inherits_from_most_trusted(self):
        r_scholar = _w("X title from scholar", doi="10.1/x", src=SourceName.GOOGLE_SCHOLAR, conf=0.5)
        r_orcid = _w("X title from orcid", doi="10.1/x", src=SourceName.ORCID, conf=1.0)
        merged = merge_records([r_scholar, r_orcid])
        # El title canónico viene del ORCID
        assert merged.title == "X title from orcid"
