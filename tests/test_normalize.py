"""Tests de normalización."""

from app.core.normalize import (
    name_initials_form,
    normalize_arxiv,
    normalize_doi,
    normalize_orcid,
    normalize_person_name,
    normalize_title,
    validate_orcid_checksum,
)


class TestNormalizeTitle:
    def test_preserves_short_math_tokens(self):
        # "p-adic" debe sobrevivir; era un bug temprano que filtraba tokens de 1 char.
        assert "p" in normalize_title("A study of p-adic Galois representations").split()
        assert "k" in normalize_title("K-theory of arithmetic schemes").split()
        assert "l" in normalize_title("L-functions in number theory").split()

    def test_removes_stopwords(self):
        n = normalize_title("The Theory of the Field of Elements")
        assert "the" not in n.split()
        assert "of" not in n.split()
        assert "theory" in n

    def test_ascii_folding(self):
        assert "perez" in normalize_title("Pérez-Buendía contribution")
        assert "berkovich" in normalize_title("Berkovich spaces and rigidity")

    def test_idempotent(self):
        t = "The p-adic L-functions of elliptic curves"
        assert normalize_title(normalize_title(t)) == normalize_title(t)

    def test_empty_input(self):
        assert normalize_title("") == ""
        assert normalize_title(None) == ""  # type: ignore[arg-type]


class TestNormalizeDoi:
    def test_strips_url_prefix(self):
        assert normalize_doi("https://doi.org/10.1007/s00029-019-0490-y") == "10.1007/s00029-019-0490-y"
        assert normalize_doi("doi:10.1112/S0010437X22000000") == "10.1112/s0010437x22000000"

    def test_lowercase(self):
        assert normalize_doi("10.1007/S00029-019-0490-Y").startswith("10.1007/")

    def test_rejects_garbage(self):
        assert normalize_doi("not a doi") is None
        assert normalize_doi("") is None
        assert normalize_doi(None) is None


class TestNormalizeArxiv:
    def test_new_format(self):
        assert normalize_arxiv("arXiv:2401.12345v2") == "2401.12345"
        assert normalize_arxiv("https://arxiv.org/abs/2401.12345") == "2401.12345"

    def test_old_format(self):
        assert normalize_arxiv("math.AG/0506172v1") == "math.AG/0506172"

    def test_rejects_garbage(self):
        assert normalize_arxiv("foo bar") is None


class TestOrcid:
    def test_valid_checksum(self):
        # https://orcid.org/0000-0002-1825-0097 es un ORCID de prueba conocido
        assert validate_orcid_checksum("0000-0002-1825-0097")

    def test_invalid_checksum(self):
        assert not validate_orcid_checksum("0000-0002-1825-0098")

    def test_normalize_from_url(self):
        assert normalize_orcid("https://orcid.org/0000-0002-1825-0097") == "0000-0002-1825-0097"

    def test_normalize_rejects_bad_checksum(self):
        assert normalize_orcid("0000-0002-1825-0098") is None


class TestNames:
    def test_person_name_ascii_lower(self):
        assert normalize_person_name("Pérez-Buendía, R.") == "perez-buendia r"

    def test_initials_form(self):
        assert name_initials_form("Rogelio Pérez Buendía") == "r perez buendia"
