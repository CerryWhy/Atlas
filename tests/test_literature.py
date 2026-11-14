"""Fase 6 (tier 2, Europe PMC): lettura della risposta e route, senza rete. Il test dal
vivo gira solo con ATLAS_NETWORK_TESTS=1."""

import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.db import connect, get_conn
from api.main import app
from api.retrieval import europepmc
from pipeline.lib import db

SAMPLE = Path(__file__).parent / "fixtures" / "europepmc_sample.json"


def test_parse_keeps_open_access_articles_with_license_and_link() -> None:
    total, articles = europepmc.parse(json.loads(SAMPLE.read_text(encoding="utf-8")))
    assert total > 0 and articles
    for a in articles:
        assert a.license and a.url.startswith("https://europepmc.org/article/")
    closed = {"resultList": {"result": [{"id": "1", "title": "x", "isOpenAccess": "N"}]}}
    assert europepmc.parse(closed) == (0, [])


def test_query_searches_title_and_abstract_open_access_only() -> None:
    assert europepmc.query_for('kidney "x"') == (
        '(TITLE:"kidney  x" OR ABSTRACT:"kidney  x") AND OPEN_ACCESS:y'
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    path = tmp_path / "atlas.db"
    conn = db.connect(path)
    db.migrate(conn)
    with conn:
        conn.execute(
            "INSERT INTO structure (fma_id, label_en) VALUES ('FMA:9000001', 'Right kidney')"
        )
    conn.close()
    asked: list[str] = []

    def fake(name: str, n: int) -> tuple[int, tuple[europepmc.Article, ...]]:
        asked.append(name)
        total, articles = europepmc.parse(json.loads(SAMPLE.read_text(encoding="utf-8")))
        return total, tuple(articles[:n])

    monkeypatch.setattr(europepmc, "search", fake)

    def override() -> Iterator[sqlite3.Connection]:
        c = connect(path)
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_conn] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_conn, None)
    assert all(not a.lower().startswith(("right", "left")) for a in asked)


def test_literature_route_cites_each_article(client: TestClient) -> None:
    body = client.get("/structure/FMA:9000001/literature", params={"n": 2}).json()
    assert body["query"].startswith('(TITLE:"kidney"')  # senza il lato
    assert len(body["articles"]) == 2
    for a in body["articles"]:
        assert a["citation"]["source"] == "europepmc"
        assert a["citation"]["license"] and a["citation"]["url"].startswith("https://")


def test_literature_unknown_structure_and_outage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.get("/structure/FMA:1/literature").status_code == 404

    def down(_name: str, _n: int) -> tuple[int, tuple[europepmc.Article, ...]]:
        raise europepmc.LiteratureUnavailable("Europe PMC non raggiungibile: timeout")

    monkeypatch.setattr(europepmc, "search", down)
    r = client.get("/structure/FMA:9000001/literature")
    assert r.status_code == 503 and "Europe PMC" in r.json()["detail"]


@pytest.mark.skipif(os.environ.get("ATLAS_NETWORK_TESTS") != "1", reason="serve la rete")
def test_live_search_returns_real_openable_articles() -> None:
    """Accettazione Fase 6 (adattata): una struttura senza documenti locali
    ("gastroduodenal artery") riceve articoli reali, open access e apribili."""
    total, articles = europepmc.search("gastroduodenal artery", 5)
    assert total > 0 and articles
    assert all(a.url.startswith("https://") and a.license for a in articles)
