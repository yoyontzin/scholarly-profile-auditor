"""Parser CSV permisivo → WorkRecord.

Columnas reconocidas (case-insensitive, separadores `_`/` `/`-` equivalentes):
    title, year, doi, arxiv, type, venue, authors, url

Si una columna 'authors' contiene separadores varios, intentamos partir por
`;`, `|`, ` and `. Esto es tolerante a la heterogeneidad real de los CSVs
de bibliotecas y exports.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from app.core.normalize import normalize_arxiv, normalize_doi, normalize_title
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType


def _normalize_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", k.lower())


def _split_authors(s: str) -> list[str]:
    if not s:
        return []
    # probar separadores en orden de probabilidad
    for sep in (";", "|", " and ", ","):
        if sep in s:
            return [a.strip() for a in s.split(sep) if a.strip()]
    return [s.strip()]


def parse_csv(path: str | Path) -> list[WorkRecord]:
    path = Path(path)
    records: list[WorkRecord] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        field_map = {_normalize_key(k): k for k in reader.fieldnames}

        def get(row: dict[str, str], *keys: str) -> str:
            for k in keys:
                fk = field_map.get(_normalize_key(k))
                if fk and row.get(fk):
                    return row[fk].strip()
            return ""

        for row in reader:
            title = get(row, "title")
            if not title:
                continue
            year_str = get(row, "year", "publication_year")
            year = int(year_str) if year_str.isdigit() else None
            doi = normalize_doi(get(row, "doi"))
            arxiv = normalize_arxiv(get(row, "arxiv", "arxiv_id", "eprint"))
            wtype_str = get(row, "type")
            wtype = WorkType.OTHER
            if wtype_str:
                for wt in WorkType:
                    if wt.value == wtype_str.lower():
                        wtype = wt
                        break
            authors = _split_authors(get(row, "authors", "author"))
            venue = get(row, "venue", "journal", "booktitle") or None
            url = get(row, "url") or None
            source = SourceRecord(
                source=SourceName.USER_FILE,
                endpoint=str(path),
                notes="CSV row",
            )
            records.append(
                WorkRecord(
                    title=title,
                    normalized_title=normalize_title(title),
                    year=year,
                    doi=doi,
                    arxiv_id=arxiv,
                    venue=venue,
                    type=wtype,
                    authors=authors,
                    url_best=url if url else None,
                    source_list=[source],
                    source_confidence={SourceName.USER_FILE: 0.6},
                    user_supplied_flag=True,
                    raw_per_source={SourceName.USER_FILE: dict(row)},
                )
            )
    return records
