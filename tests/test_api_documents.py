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


def test_merge_keeps_one_hit_per_document_nearest_first() -> None:
    hits = [
        ("a#3", "a", 0.30),
        ("a#0", "a", 0.10),  # titolo di "a": vince sul suo paragrafo più lontano
        ("b#1", "b", 0.20),
        ("c#0", "c", 0.20),
        ("a#5", "a", 0.05),  # ...ma un paragrafo ancora più vicino vince sul titolo
    ]
    assert local.merge_by_document(hits, 2) == [("a#5", "a", 0.05), ("b#1", "b", 0.20)]
    assert local.merge_by_document([], 3) == []


def test_a_document_found_by_title_comes_first_with_its_first_chunk(
    client: TestClient, tmp_path: Path
) -> None:
    """La domanda è vicina al TITOLO di medlineplus:1 più che a qualunque paragrafo."""
    conn = sqlite3.connect(tmp_path / "atlas.db")
    vec.load(conn)
    with conn:
        vec.insert_titles(conn, [("medlineplus:1", "Hepatitis", [0.9, 0.1, 0.0, 0.0])])
    conn.close()
    hits = client.get("/search", params={"q": "epatite", "k": 2}).json()
    assert [h["doc_id"] for h in hits] == ["medlineplus:1", "statpearls:article-1"]
    assert hits[0]["chunk_id"] == "medlineplus:1#0" and hits[0]["text"] == "Hepatitis is..."
    assert len({h["doc_id"] for h in hits}) == len(hits)  # un risultato per documento


def test_search_works_on_an_index_built_before_title_vectors(
    client: TestClient, tmp_path: Path
) -> None:
    conn = sqlite3.connect(tmp_path / "atlas.db")
    vec.load(conn)
    with conn:
        conn.execute("DROP TABLE title_vec")
    conn.close()
    hits = client.get("/search", params={"q": "fegato", "k": 2}).json()
    assert [h["doc_id"] for h in hits] == ["statpearls:article-1", "medlineplus:1"]


def test_a_changed_title_gets_a_new_vector(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    vec.load(conn)
    db.migrate(conn)
    with conn:
        db.upsert_document(conn, ("d:1", "s", "Old", "http://x", "CC BY 4.0", "2026", "t", "h"))
        vec.ensure(conn, "m", 4)
        vec.insert_titles(conn, [("d:1", "Old", [1, 0, 0, 0])])
        assert vec.titles_without_vectors(conn, 10) == []
        db.upsert_document(conn, ("d:1", "s", "New", "http://x", "CC BY 4.0", "2026", "t", "h"))
        assert vec.delete_orphans(conn) == 1
    assert vec.titles_without_vectors(conn, 10) == [("d:1", "New")]
