"""Parser CSL-JSON → WorkRecord.

CSL-JSON (Citation Style Language JSON) es el formato canónico de Zotero, Pandoc,
y muchas herramientas modernas. Estructura: array de objetos con campos como
`type`, `title`, `author` (array), `issued.date-parts`, `DOI`, etc.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.normalize import normalize_arxiv, normalize_doi, normalize_title
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

_CSL_TYPE_MAP: dict[str, WorkType] = {
    "article-journal": WorkType.JOURNAL_ARTICLE,
    "article": WorkType.JOURNAL_ARTICLE,
    "paper-conference": WorkType.CONFERENCE_PAPER,
    "chapter": WorkType.BOOK_CHAPTER,
    "book": WorkType.BOOK,
    "thesis": WorkType.THESIS,
    "report": WorkType.REPORT,
    "manuscript": WorkType.PREPRINT,
    "dataset": WorkType.DATASET,
    "software": WorkType.SOFTWARE,
    "webpage": WorkType.OTHER,
}


def parse_csl_json(path: str | Path) -> list[WorkRecord]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    records: list[WorkRecord] = []
    for item in data:
        title = item.get("title")
        if not title:
            continue
        wtype = _CSL_TYPE_MAP.get(item.get("type", "").lower(), WorkType.OTHER)
        doi = normalize_doi(item.get("DOI") or item.get("doi"))
        arxiv_id = normalize_arxiv(item.get("URL") or item.get("note"))
        year = None
        issued = item.get("issued") or {}
        parts = issued.get("date-parts") or []
        if parts and parts[0]:
            try:
                year = int(parts[0][0])
            except (ValueError, TypeError):
                year = None
        authors = []
        for a in (item.get("author") or []):
            given = a.get("given", "")
            family = a.get("family", "")
            literal = a.get("literal")
            full = literal or " ".join(p for p in (given, family) if p)
            if full:
                authors.append(full)
        venue = item.get("container-title")
        source = SourceRecord(
            source=SourceName.USER_FILE,
            endpoint=str(path),
            raw_id=item.get("id"),
            notes="CSL-JSON item",
        )
        records.append(
            WorkRecord(
                title=title,
                normalized_title=normalize_title(title),
                year=year,
                doi=doi,
                arxiv_id=arxiv_id,
                venue=venue,
                type=wtype,
                authors=authors,
                publisher=item.get("publisher"),
                source_list=[source],
                source_confidence={SourceName.USER_FILE: 0.75},
                user_supplied_flag=True,
                raw_per_source={SourceName.USER_FILE: item},
            )
        )
    return records
