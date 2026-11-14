"""POST /locate su un database sintetico: la codifica del testo è sostituita da un
vettore fisso (niente modello). ID segnaposto."""

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
        conn.execute(
            "INSERT INTO source_release (source, title, version, url, license, attribution)"
            " VALUES ('hpo', 'HPO', 'v1', 'https://hpo.jax.org/', 'HPO license', 't')"
        )
        conn.executemany(
            "INSERT INTO structure (fma_id, label_en, label_it, cx, cy, cz, radius, mesh_node)"
            " VALUES (?, ?, ?, 0, 0, 0, 1, ?)",
            [
                ("FMA:9000001", "Heart", "cuore", "FMA:9000001"),
                ("FMA:9000002", "Vertebral column", None, "FMA:9000002"),
                ("FMA:9000003", "Cardiovascular system", None, None),
            ],
        )
        db.upsert_phenotypes(
            conn,
            [
                ("HP:9000001", "Cardiomegaly", None, 0, "Enlarged heart"),
                ("HP:9000002", "Back pain", None, 0, None),
                ("HP:9000003", "Abnormality of the vertebral column", None, 0, None),
                ("HP:9000004", "Palpitations", None, 0, None),
            ],
        )
        db.replace_phenotype_loci(
            conn,
            [
                ("HP:9000001", "FMA:9000001", "UBERON:9000001", "logical", "HP:9000001", 0),
                ("HP:9000002", "FMA:9000002", "UBERON:9000002", "inherited", "HP:9000003", 1),
                ("HP:9000004", "FMA:9000003", "UBERON:9000003", "inherited", "HP:9000001", 3),
            ],
        )
        vec.ensure_phenotypes(conn, "test-model", 4)
        vec.insert_phenotypes(
            conn,
            [
                ("HP:9000001#0", "Cardiomegaly", [1, 0, 0, 0]),
                ("HP:9000001#1", "Enlarged heart", [0.9, 0.1, 0, 0]),
                ("HP:9000004#0", "Palpitations", [0.7, 0.3, 0, 0]),
                ("HP:9000002#0", "Back pain", [0, 0, 1, 0]),
            ],
        )
    conn.close()

    def override() -> Iterator[sqlite3.Connection]:
        c = connect(path)
        try:
            yield c
        finally:
            c.close()

    monkeypatch.setattr(local, "encode_query", lambda _c, _t, _m="": vec.serialize([1, 0, 0, 0]))
    app.dependency_overrides[get_conn] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_conn, None)


def test_locate_ranks_structures_by_the_nearest_phenotype(client: TestClient) -> None:
    body = client.post("/locate", json={"text": "cuore ingrossato"}).json()
    assert [s["fma_id"] for s in body["structures"]] == [
        "FMA:9000001",
        "FMA:9000003",
        "FMA:9000002",
    ]
    heart = body["structures"][0]
    assert heart["mesh_nodes"] == ["FMA:9000001"] and heart["centroid"] == [0, 0, 0]
    assert heart["phenotypes"] == ["HP:9000001"]
    # un fenotipo trovato da due nomi conta una volta
    assert [p["hpo_id"] for p in body["phenotypes"]].count("HP:9000001") == 1


def test_inherited_sites_cite_the_ancestor(client: TestClient) -> None:
    body = client.post("/locate", json={"text": "x x"}).json()
    back = next(p for p in body["phenotypes"] if p["hpo_id"] == "HP:9000002")
    assert back["basis"] == "inherited"
    assert back["via_label"] == "Abnormality of the vertebral column"
    assert len(back["citations"]) == 2
    assert "sottoclasse di Abnormality of the vertebral column" in back["citations"][1]["title"]
    heart = next(p for p in body["phenotypes"] if p["hpo_id"] == "HP:9000001")
    assert heart["basis"] == "logical" and len(heart["citations"]) == 1


def test_locate_rejects_empty_or_too_long_text(client: TestClient) -> None:
    assert client.post("/locate", json={"text": "x"}).status_code == 422
    assert client.post("/locate", json={"text": "x" * 301}).status_code == 422


def test_names_to_embed_include_synonyms_once(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.migrate(conn)
    with conn:
        conn.execute("INSERT INTO structure (fma_id, label_en) VALUES ('FMA:1', 'Heart')")
        db.upsert_phenotypes(
            conn,
            [
                ("HP:0000001", "Cardiomegaly", None, 0, "Enlarged heart | cardiomegaly"),
                ("HP:0000002", "Orphan", None, 0, None),  # nessun locus: non indicizzato
            ],
        )
        db.replace_phenotype_loci(
            conn, [("HP:0000001", "FMA:1", "UBERON:1", "logical", "HP:0000001", 0)]
        )
    assert db.phenotypes_to_embed(conn) == [
        ("HP:0000001#0", "Cardiomegaly"),
        ("HP:0000001#1", "Enlarged heart"),
    ]
