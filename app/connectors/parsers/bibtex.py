"""Parser BibTeX → WorkRecord, vía bibtexparser."""

from __future__ import annotations

from pathlib import Path

import bibtexparser  # type: ignore

from app.core.normalize import normalize_arxiv, normalize_doi, normalize_title
from app.models.source import SourceName, SourceRecord
from app.models.work import WorkRecord, WorkType

_BIB_TYPE_MAP: dict[str, WorkType] = {
    "article": WorkType.JOURNAL_ARTICLE,
    "inproceedings": WorkType.CONFERENCE_PAPER,
    "conference": WorkType.CONFERENCE_PAPER,
    "incollection": WorkType.BOOK_CHAPTER,
    "inbook": WorkType.BOOK_CHAPTER,
    "book": WorkType.BOOK,
    "phdthesis": WorkType.THESIS,
    "mastersthesis": WorkType.THESIS,
    "techreport": WorkType.REPORT,
    "unpublished": WorkType.PREPRINT,
    "misc": WorkType.OTHER,
    "software": WorkType.SOFTWARE,
    "dataset": WorkType.DATASET,
}


def parse_bibtex(path: str | Path) -> list[WorkRecord]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        db = bibtexparser.load(f)
    records: list[WorkRecord] = []
    for entry in db.entries:
        title = entry.get("title", "").strip("{}").strip()
        if not title:
            continue
        wtype = _BIB_TYPE_MAP.get(entry.get("ENTRYTYPE", "").lower(), WorkType.OTHER)
        year = entry.get("year")
        year_int = int(year) if year and year.isdigit() else None
        doi = normalize_doi(entry.get("doi"))
        arxiv_id = normalize_arxiv(entry.get("eprint") or entry.get("archiveprefix"))
        authors_str = entry.get("author", "")
        authors = [a.strip() for a in authors_str.split(" and ") if a.strip()]
        venue = entry.get("journal") or entry.get("booktitle")
        source = SourceRecord(
            source=SourceName.USER_FILE,
            endpoint=str(path),
            raw_id=entry.get("ID"),
            notes=f"BibTeX entry @{entry.get('ENTRYTYPE')}",
        )
        records.append(
            WorkRecord(
                title=title,
                normalized_title=normalize_title(title),
                year=year_int,
                doi=doi,
                arxiv_id=arxiv_id,
                venue=venue,
                type=wtype,
                authors=authors,
                publisher=entry.get("publisher"),
                source_list=[source],
                source_confidence={SourceName.USER_FILE: 0.7},
                user_supplied_flag=True,
                raw_per_source={SourceName.USER_FILE: dict(entry)},
            )
        )
    return records
