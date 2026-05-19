"""Tests de parsers."""

from pathlib import Path

from app.connectors.parsers import parse_user_file


def test_parse_bibtex(tmp_path: Path):
    p = tmp_path / "refs.bib"
    p.write_text("""
@article{padic2024,
  title = {The p-adic structure of GRNs},
  author = {P{\\'e}rez-Buend{\\'\\i}a, R. and Nopal-Coello, M.},
  year = {2024},
  journal = {Chaos},
  doi = {10.1016/j.csf.2024.000},
  eprint = {2603.14097}
}
""")
    recs = parse_user_file(p)
    assert len(recs) == 1
    r = recs[0]
    assert "p-adic" in r.title.lower() or r.normalized_title.startswith("p")
    assert r.doi == "10.1016/j.csf.2024.000"
    assert r.arxiv_id == "2603.14097"
    assert r.year == 2024
    assert r.user_supplied_flag


def test_parse_csl_json(tmp_path: Path):
    p = tmp_path / "refs.json"
    p.write_text('''[
      {"id":"X","type":"article-journal","title":"Test",
       "author":[{"given":"R","family":"Pérez-Buendía"}],
       "issued":{"date-parts":[[2022]]},"DOI":"10.1/X"}
    ]''')
    recs = parse_user_file(p)
    assert len(recs) == 1
    assert recs[0].year == 2022
    assert recs[0].doi == "10.1/x"


def test_parse_csv(tmp_path: Path):
    p = tmp_path / "refs.csv"
    p.write_text("title,year,doi,authors\nA paper,2024,10.5/x,A; B; C\n")
    recs = parse_user_file(p)
    assert len(recs) == 1
    assert recs[0].authors == ["A", "B", "C"]


def test_unsupported_extension_returns_empty(tmp_path: Path):
    p = tmp_path / "weird.xyz"
    p.write_text("not parseable")
    recs = parse_user_file(p)
    assert recs == []
