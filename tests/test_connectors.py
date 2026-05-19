"""Tests de conectores con HTTP mockeado vía respx."""

import httpx
import pytest
import respx

from app.connectors.base import BaseConnector
from app.connectors.crossref import CrossrefConnector
from app.connectors.openalex import OpenAlexConnector


@pytest.fixture(autouse=True)
async def _close_client():
    yield
    await BaseConnector.close_client()


@respx.mock
async def test_crossref_message_to_record():
    sample = {
        "message": {
            "DOI": "10.1234/test",
            "title": ["A test paper"],
            "type": "journal-article",
            "issued": {"date-parts": [[2024, 1, 1]]},
            "author": [
                {"given": "Rogelio", "family": "Pérez-Buendía",
                 "ORCID": "https://orcid.org/0000-0002-1825-0097"},
            ],
            "container-title": ["Annals of Math"],
        }
    }
    respx.get("https://api.crossref.org/works/10.1234/test").mock(
        return_value=httpx.Response(200, json=sample)
    )
    c = CrossrefConnector()
    msg = await c.fetch_by_doi("10.1234/test")
    assert msg is not None
    rec = c.message_to_record(msg)
    assert rec is not None
    assert rec.title == "A test paper"
    assert rec.doi == "10.1234/test"
    assert rec.year == 2024
    assert rec.coauthor_orcids == ["0000-0002-1825-0097"]


@respx.mock
async def test_openalex_pagination_stops_on_empty_cursor():
    page = {
        "results": [
            {"id": "https://openalex.org/W1", "title": "P1",
             "publication_year": 2023, "type": "journal-article",
             "authorships": [], "cited_by_count": 10},
        ],
        "meta": {"next_cursor": None},
    }
    respx.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=page)
    )
    c = OpenAlexConnector()
    works = await c.fetch_works_by_orcid("0000-0002-1825-0097", max_pages=5)
    assert len(works) == 1
    rec = c.work_to_record(works[0])
    assert rec.title == "P1"
    assert rec.citation_counts_by_source[0].count == 10


@respx.mock
async def test_retry_on_503():
    """Verifica que 503 dispara retry y eventualmente devuelve 200."""
    route = respx.get("https://api.crossref.org/works/10.5/retry")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json={"message": {"DOI": "10.5/retry", "title": ["OK"], "type": "journal-article"}}),
    ]
    c = CrossrefConnector()
    msg = await c.fetch_by_doi("10.5/retry")
    assert msg is not None
    assert msg["title"] == ["OK"]
