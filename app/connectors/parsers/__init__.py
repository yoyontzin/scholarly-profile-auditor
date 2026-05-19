"""Parsers de archivos de referencias subidos por el usuario.

Dispatcher por extensión: el flujo principal solo llama parse_user_file()
y recibe una lista de WorkRecord uniforme.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.models.work import WorkRecord

from .bibtex import parse_bibtex
from .csl_json import parse_csl_json
from .csv_parser import parse_csv
from .ris import parse_ris

logger = get_logger(__name__)


def parse_user_file(path: str | Path) -> list[WorkRecord]:
    """Detecta formato por extensión y delega al parser correcto."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".bib":
        return parse_bibtex(p)
    if ext == ".ris":
        return parse_ris(p)
    if ext in (".csv", ".tsv"):
        return parse_csv(p)
    if ext == ".json":
        # heurística: CSL-JSON o JSON genérico → tratar como CSL-JSON
        return parse_csl_json(p)
    logger.warning("Formato no soportado: %s. Devolviendo lista vacía.", ext)
    return []


__all__ = ["parse_user_file", "parse_bibtex", "parse_ris", "parse_csv", "parse_csl_json"]
