"""Letture nella scheda e ricerca vettoriale, su un database sintetico (senza modello:
la codifica della domanda è sostituita da un vettore fisso). ID segnaposto."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.db import connect, get_conn
from api.main import app
from api.retrieval import local
from pipeline.lib import db, vec


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    path = tmp_path / "atlas.db"
    conn = db.connect(path)
    vec.load(conn)
    db.migrate(conn)
    with conn:
        conn.executemany(
            "INSERT INTO source_release (source, title, version, url, license, attribution)"
            " VALUES (?, ?, 'v1', 'http://example.org', 'CC BY 4.0', 'test')",
            [(s, s) for s in ("fma", "bodyparts3d")],
        )
        conn.execute("INSERT INTO structure (fma_id, label_en) VALUES ('FMA:9999991', 'Liver')")
        conn.execute("INSERT INTO disease (mondo_id, label) VALUES ('MONDO:9999999', 'hepatitis')")
        docs = [
            (
                "statpearls:article-1",
                "statpearls",
                "Anatomy, Abdomen and Pelvis, Liver",
                "https://www.ncbi.nlm.nih.gov/books/n/statpearls/article-1/",
                "CC BY-NC-ND 4.0",
            ),
            (
                "medlineplus:1",
                "medlineplus",
                "Hepatitis",
                "https://medlineplus.gov/h.html",
                "Public domain (U.S. government work)",
            ),
        ]
        for doc_id, source, title, url, lic in docs:
            db.upsert_document(conn, (doc_id, source, title, url, lic, "2026-11-13", title, "x"))
        db.replace_document_links(
            conn,
            [("medlineplus:1", "MONDO:9999999", "mondo_xref_mesh", "MESH:D0")],
            [
                ("statpearls:article-1", "FMA:9999991", 1.0, "anatomy_title", "liver"),
                ("medlineplus:1", "FMA:9999991", 0.5, "disease_site", "MONDO:9999999"),
            ],
        )
        db.insert_chunks(
            conn,
            [
                ("statpearls:article-1#0", "statpearls:article-1", 0, "The liver lies..."),
                ("medlineplus:1#0", "medlineplus:1", 0, "Hepatitis is..."),
            ],
        )
        vec.ensure(conn, "test-model", 4)
        vec.insert(
            conn,
            [("statpearls:article-1#0", [1, 0, 0, 0]), ("medlineplus:1#0", [0, 1, 0, 0])],
        )
    conn.close()

    def override() -> Iterator[sqlite3.Connection]:
        c = connect(path)
        try:
            yield c
        finally:
            c.close()

    monkeypatch.setattr(local, "encode_query", lambda _c, _t: vec.serialize([0.9, 0.1, 0.0, 0.0]))
    app.dependency_overrides[get_conn] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_conn, None)


def test_readings_are_ordered_and_cite_their_document(client: TestClient) -> None:
    docs = client.get("/structure/FMA:9999991").json()["documents"]
    assert [d["doc_id"] for d in docs] == ["statpearls:article-1", "medlineplus:1"]
    assert docs[0]["link"] == "Tratta questa struttura"
    assert docs[1]["link"] == "Tramite la malattia: hepatitis"
    cite = docs[0]["citation"]
    assert cite["license"] == "CC BY-NC-ND 4.0" and cite["url"].startswith("https://www.ncbi")


def test_search_returns_cited_chunks_nearest_first(client: TestClient) -> None:
    hits = client.get("/search", params={"q": "fegato", "k": 2}).json()
    assert [h["chunk_id"] for h in hits] == ["statpearls:article-1#0", "medlineplus:1#0"]
    assert hits[0]["score"] > hits[1]["score"]
    assert hits[0]["citation"]["title"] == "Anatomy, Abdomen and Pelvis, Liver"


def test_search_without_vectors_says_why(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_c: object, _t: str) -> bytes:
        raise local.SearchUnavailable("nessun vettore")

    monkeypatch.setattr(local, "encode_query", unavailable)
    r = client.get("/search", params={"q": "fegato"})
    assert r.status_code == 503 and "vettore" in r.json()["detail"]
