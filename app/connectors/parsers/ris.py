"""Parser RIS → WorkRecord, vía rispy."""

from __future__ import annotations

from pathlib import Path

import rispy  # type: ignore

from app.core.normalize import normalize_doi, normalize_title
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

_RIS_TYPE_MAP: dict[str, WorkType] = {
    "JOUR": WorkType.JOURNAL_ARTICLE,
    "CONF": WorkType.CONFERENCE_PAPER,
    "CPAPER": WorkType.CONFERENCE_PAPER,
    "CHAP": WorkType.BOOK_CHAPTER,
    "BOOK": WorkType.BOOK,
    "THES": WorkType.THESIS,
    "RPRT": WorkType.REPORT,
    "DATA": WorkType.DATASET,
    "COMP": WorkType.SOFTWARE,
    "GEN": WorkType.OTHER,
}


def parse_ris(path: str | Path) -> list[WorkRecord]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        entries = rispy.load(f)
    records: list[WorkRecord] = []
    for e in entries:
        title = e.get("title") or e.get("primary_title") or ""
        if not title:
            continue
        wtype = _RIS_TYPE_MAP.get(e.get("type_of_reference", ""), WorkType.OTHER)
        year = e.get("year") or e.get("publication_year")
        year_int = int(year) if year and str(year).isdigit() else None
        authors = (
            e.get("authors")
            or e.get("first_authors")
            or e.get("secondary_authors")
            or []
        )
        doi = normalize_doi(e.get("doi"))
        venue = e.get("journal_name") or e.get("secondary_title")
        source = SourceRecord(
            source=SourceName.USER_FILE,
            endpoint=str(path),
            raw_id=e.get("id"),
            notes="RIS entry",
        )
        records.append(
            WorkRecord(
                title=title,
                normalized_title=normalize_title(title),
                year=year_int,
                doi=doi,
                venue=venue,
                type=wtype,
                authors=list(authors) if isinstance(authors, list) else [authors],
                source_list=[source],
                source_confidence={SourceName.USER_FILE: 0.7},
                user_supplied_flag=True,
                raw_per_source={SourceName.USER_FILE: e},
            )
        )
    return records
