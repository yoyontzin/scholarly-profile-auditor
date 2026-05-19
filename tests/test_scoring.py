"""Tests del scoring de autoría."""

from app.core.normalize import normalize_title
from app.models.author import AuthorProfile
from app.models.source import SourceName, SourceRecord
from app.models.verification import VerificationStatus
from app.models.work import WorkRecord, WorkType
from app.reconciliation.scoring import AuthorContext, score_work


def _author():
    return AuthorProfile(
        orcid="0000-0002-1825-0097",
        display_name="Rogelio Pérez-Buendía",
        given_names="Rogelio",
        family_names="Pérez-Buendía",
        affiliations=["CIMAT"],
    )


def _w(title, **kw):
    src = kw.pop("src", SourceName.OPENALEX)
    kw.setdefault("source_list", [SourceRecord(source=src)])
    kw.setdefault("source_confidence", {src: 0.8})
    return WorkRecord(
        title=title,
        normalized_title=normalize_title(title),
        type=WorkType.JOURNAL_ARTICLE,
        **kw,
    )


class TestScoring:
    def test_orcid_explicit_confirms(self):
        ctx = AuthorContext.build(_author(), career_start_year=2010)
        w = _w(
            "A paper",
            year=2024,
            doi="10.1/a",
            authors=["R. Pérez-Buendía"],
            coauthor_orcids=["0000-0002-1825-0097"],
        )
        d = score_work(w, ctx)
        assert d.status == VerificationStatus.CONFIRMED
        assert "orcid_explicit" in d.signals

    def test_no_stable_id_blocks_confirm(self):
        """Política dura: sin DOI/arXiv/ISBN no se puede confirmar (salvo ORCID explícito)."""
        ctx = AuthorContext.build(_author(), career_start_year=2010)
        # Nombre exacto + año plausible + segunda fuente, pero NO DOI ni ORCID explícito
        w = _w(
            "A paper without identifiers",
            year=2024,
            authors=["Rogelio Pérez-Buendía"],
            source_list=[
                SourceRecord(source=SourceName.OPENALEX),
                SourceRecord(source=SourceName.ORCID),
            ],
            source_confidence={SourceName.OPENALEX: 0.8, SourceName.ORCID: 1.0},
        )
        d = score_work(w, ctx)
        # Aun con score alto, sin identificador estable → probable, no confirmed
        assert d.status != VerificationStatus.CONFIRMED

    def test_random_paper_rejected(self):
        ctx = AuthorContext.build(_author(), career_start_year=2010)
        w = _w(
            "Quantum entanglement in superconductors",
            year=2024,
            doi="10.9/x",
            authors=["John Doe", "Jane Smith"],
        )
        d = score_work(w, ctx)
        assert d.status == VerificationStatus.REJECTED

    def test_arxiv_with_name_match_is_ambiguous(self):
        ctx = AuthorContext.build(_author(), career_start_year=2010)
        w = _w(
            "Berkovich dynamics on gene networks",
            year=2023,
            arxiv_id="2401.00001",
            authors=["R. Pérez-Buendía"],
        )
        d = score_work(w, ctx)
        # arXiv + name → ambiguo (sin ORCID ni 2da fuente)
        assert d.status == VerificationStatus.AMBIGUOUS
        assert d.requires_review

    def test_user_supplied_boosts_score(self):
        ctx = AuthorContext.build(_author(), career_start_year=2010)
        w = _w(
            "A paper present in user file",
            year=2024,
            doi="10.5/a",
            user_supplied_flag=True,
            authors=["R. Pérez-Buendía"],
        )
        d = score_work(w, ctx)
        assert "title_in_user_file" in d.signals
        assert d.status == VerificationStatus.CONFIRMED
