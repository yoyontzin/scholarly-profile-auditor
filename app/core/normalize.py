"""Normalización: títulos, DOIs, arXiv IDs, ORCIDs, nombres."""

from __future__ import annotations

import re

from unidecode import unidecode

# ---------------------------------------------------------------------------
# Títulos
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")
_STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "in", "on", "for", "to", "with",
    "by", "at", "from", "as", "is", "are", "be",
}


def normalize_title(title: str) -> str:
    """Forma canónica de un título para matching robusto.

    Pasos: ASCII, lowercase, sin puntuación, sin stopwords, sin espacios extra.
    Empíricamente esto reduce falsos negativos de matching entre fuentes
    sin requerir LLMs.
    """
    if not title:
        return ""
    t = unidecode(title).lower()
    t = _PUNCT_RE.sub(" ", t)
    # No filtramos por longitud: en matemáticas tokens cortos importan
    # ("p-adic", "L-functions", "k-theory"). Solo se eliminan stopwords.
    tokens = [w for w in t.split() if w not in _STOPWORDS]
    return _WHITESPACE_RE.sub(" ", " ".join(tokens)).strip()


# ---------------------------------------------------------------------------
# DOI
# ---------------------------------------------------------------------------

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)


def normalize_doi(raw: str | None) -> str | None:
    """Normaliza un DOI: minúsculas, sin prefijo URL, sin espacios."""
    if not raw:
        return None
    s = raw.strip()
    # quitar URL
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "DOI:"):
        if s.lower().startswith(prefix.lower()):
            s = s[len(prefix):]
    s = s.strip().lower()
    m = _DOI_RE.search(s)
    return m.group(0) if m else (s if s.startswith("10.") else None)


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

_ARXIV_NEW = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b")           # 2401.12345
_ARXIV_OLD = re.compile(r"\b([a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?\b", re.IGNORECASE)


def normalize_arxiv(raw: str | None) -> str | None:
    """Devuelve el arXiv ID sin versión, sin prefijo."""
    if not raw:
        return None
    s = raw.strip()
    for prefix in (
        "https://arxiv.org/abs/",
        "http://arxiv.org/abs/",
        "arxiv:",
        "arXiv:",
    ):
        if s.lower().startswith(prefix.lower()):
            s = s[len(prefix):]
    m = _ARXIV_NEW.search(s) or _ARXIV_OLD.search(s)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# ORCID
# ---------------------------------------------------------------------------

_ORCID_RE = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")


def normalize_orcid(raw: str | None) -> str | None:
    """Extrae 0000-0002-XXXX-XXXX de cualquier URL o cadena."""
    if not raw:
        return None
    s = raw.strip()
    m = _ORCID_RE.search(s)
    if not m:
        return None
    orcid = m.group(0)
    return orcid if validate_orcid_checksum(orcid) else None


def validate_orcid_checksum(orcid: str) -> bool:
    """Valida el checksum ISO 7064 mod 11-2 del ORCID iD."""
    digits = orcid.replace("-", "")
    if len(digits) != 16:
        return False
    total = 0
    for ch in digits[:-1]:
        if not ch.isdigit():
            return False
        total = (total + int(ch)) * 2
    remainder = total % 11
    result = (12 - remainder) % 11
    check = "X" if result == 10 else str(result)
    return check == digits[-1].upper()


# ---------------------------------------------------------------------------
# Nombres de autor
# ---------------------------------------------------------------------------

_LATEX_APOSTROPHES = re.compile(r"[‘’‚ʼʼ]")  # U+2018 U+2019 U+201A U+02BC


def normalize_person_name(name: str) -> str:
    """Forma canónica para matching de nombres: ASCII, lowercase, sin puntos.

    Importante: algunos endpoints (Semantic Scholar) serializan acentos como
    apóstrofes Unicode + letra (LaTeX-style: "P'erez-Buend'ia" para "Pérez-Buendía").
    Estos apóstrofes se eliminan antes del unidecode para evitar falsos negativos
    cuando se compara contra nombres bien formados.
    """
    if not name:
        return ""
    n = _LATEX_APOSTROPHES.sub("", name)
    n = unidecode(n).lower()
    n = re.sub(r"[\.,]", " ", n)
    n = _WHITESPACE_RE.sub(" ", n).strip()
    return n


def name_initials_form(name: str) -> str:
    """'Rogelio Pérez Buendía' → 'r perez buendia'."""
    n = normalize_person_name(name)
    parts = n.split()
    if not parts:
        return ""
    return " ".join([parts[0][0]] + parts[1:])
