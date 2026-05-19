"""Tests de métricas y SNII."""

from app.core.normalize import normalize_title
from app.metrics.citations import compute_metrics, h_index, i10_index
from app.metrics.snii import build_snii_summary, consolidate_citations_max_per_work
from app.models.citation import CitationCount
from app.models.source import SourceName, SourceRecord
from app.models.verification import VerificationDecision, VerificationStatus
from app.models.work import WorkRecord, WorkType


def _confirmed_work(title, year, citations):
    cc = [CitationCount(source=s, count=c) for s, c in citations.items()]
    w = WorkRecord(
        title=title,
        normalized_title=normalize_title(title),
        year=year,
        type=WorkType.JOURNAL_ARTICLE,
        source_list=[SourceRecord(source=s) for s in citations.keys()],
        source_confidence={s: 0.9 for s in citations.keys()},
        citation_counts_by_source=cc,
    )
    w.verification = VerificationDecision(
        status=VerificationStatus.CONFIRMED, score=1.0, reasons=["test"]
    )
    return w


class TestHIndex:
    def test_basic(self):
        assert h_index([10, 8, 5, 4, 3]) == 4
        assert h_index([100, 1, 1, 1]) == 1
        assert h_index([]) == 0

    def test_i10(self):
        assert i10_index([12, 10, 9, 8]) == 2
        assert i10_index([1, 2, 3]) == 0


class TestCitationsBySource:
    def test_no_summing_between_sources(self):
        works = [
            _confirmed_work("A", 2023, {SourceName.OPENALEX: 5, SourceName.GOOGLE_SCHOLAR: 12}),
            _confirmed_work("B", 2024, {SourceName.OPENALEX: 3, SourceName.GOOGLE_SCHOLAR: 8}),
        ]
        m = compute_metrics(works)
        assert m.by_source[SourceName.OPENALEX] == 8
        assert m.by_source[SourceName.GOOGLE_SCHOLAR] == 20
        # Verificar que NO suma entre fuentes
        assert m.by_source[SourceName.OPENALEX] != m.by_source[SourceName.GOOGLE_SCHOLAR]


class TestSnii:
    def test_never_emits_automatic_level(self):
        works = [_confirmed_work("X", 2024, {SourceName.OPENALEX: 5})]
        m = compute_metrics(works)
        s = build_snii_summary(works, m, area="fisico_matematicas")
        # Política dura del proyecto
        assert s["automatic_level"] is None
        assert s["emit_automatic_level"] is False

    def test_disclaimer_present(self):
        works = [_confirmed_work("X", 2024, {SourceName.OPENALEX: 5})]
        m = compute_metrics(works)
        s = build_snii_summary(works, m)
        assert "no emite un dictamen" in s["disclaimer"].lower()

    def test_max_per_work_arithmetic(self):
        works = [
            _confirmed_work("A", 2024, {SourceName.OPENALEX: 5, SourceName.GOOGLE_SCHOLAR: 12}),
            _confirmed_work("B", 2024, {SourceName.OPENALEX: 7}),
        ]
        # max_per_work: max(5,12) + max(7) = 12 + 7 = 19
        assert consolidate_citations_max_per_work(works) == 19

    def test_scholar_only_warning(self):
        # 1 obra solo-Scholar de 2 → 50% solo-Scholar → debe disparar advertencia
        works = [
            _confirmed_work("A", 2024, {SourceName.GOOGLE_SCHOLAR: 5}),
            _confirmed_work("B", 2024, {SourceName.OPENALEX: 7}),
        ]
        # Marcar A como solo-scholar en source_confidence
        works[0].source_confidence = {SourceName.GOOGLE_SCHOLAR: 0.5}
        m = compute_metrics(works)
        s = build_snii_summary(works, m)
        # Debe estar la advertencia
        assert any("Scholar" in w for w in s["warnings"])
