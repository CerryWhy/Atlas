"""Test dell'API su un database sintetico minimo: girano senza la pipeline.

Gli ID qui sono segnaposto di test (FMA:999999x, Q9999999, ...), non dati: non finiscono mai
in atlas.db.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.db import connect, get_conn
from api.main import app
from pipeline.lib import db


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "atlas.db"
    conn = db.connect(path)
    db.migrate(conn)
    with conn:
        conn.executemany(
            "INSERT INTO source_release (source, title, version, url, license, attribution)"
            " VALUES (?, ?, 'v1', 'http://example.org', 'CC BY 4.0', 'test')",
            [(s, s.upper()) for s in ("fma", "uberon", "mondo", "hpo", "bodyparts3d", "wikidata")],
        )
        conn.executemany(
            "INSERT INTO structure (fma_id, label_en, label_it, label_it_source, label_it_ref,"
            " region) VALUES (?, ?, ?, ?, ?, 'thorax')",
            [
                ("FMA:9999991", "Right fourth rib", None, None, None),
                ("FMA:9999992", "Rib", "costola", "wikidata", "Q9999999"),
            ],
        )
        conn.execute(
            "INSERT INTO disease (mondo_id, label) VALUES ('MONDO:9999999', 'Rib fracture')"
        )
        conn.execute(
            "INSERT INTO disease_structure (mondo_id, uberon_id, source) "
            "VALUES ('MONDO:9999999', 'UBERON:9999999', 'mondo')"
        )
        conn.execute("INSERT INTO phenotype (hpo_id, label) VALUES ('HP:9999999', 'Rib anomaly')")
        conn.execute(
            "INSERT INTO phenotype_structure (hpo_id, uberon_id) "
            "VALUES ('HP:9999999', 'UBERON:9999999')"
        )
        db.replace_structure_uberon(
            conn,
            [
                ("FMA:9999992", "UBERON:9999999", "xref", None, None, None),
                ("FMA:9999991", "UBERON:9999999", "fma_is_a", "FMA:9999992", "Rib", "Rib"),
            ],
        )
    conn.close()

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


def test_is_a_inheritance_is_declared_and_cited(client: TestClient) -> None:
    body = client.get("/structure/FMA:9999991").json()
    [link] = body["inherited_from"]
    assert (link["basis"], link["unsided_label"], link["carries_content"]) == (
        "fma_is_a",
        "Rib",
        True,
    )
    relation, target = link["citations"]
    assert relation["source"] == "fma"
    assert "discende per sottoclasse da Rib (FMA:9999992)" in relation["title"]
    assert target["source"] == "uberon"

    items = [*body["diseases"], *body["phenotypes"]]
    assert [i["label"] for i in items] == ["Rib fracture", "Rib anomaly"]
    # I2: ogni voce ereditata cita chi asserisce la sede E la relazione di sottoclasse
    for item in items:
        assert item["inherited"]
        assert item["citations"][0]["source"] in {"mondo", "hpo"}
        assert relation in item["citations"]


def test_the_ancestor_itself_is_not_marked_inherited(client: TestClient) -> None:
    body = client.get("/structure/FMA:9999992").json()
    assert body["inherited_from"] == []
    assert body["diseases"] and not any(d["inherited"] for d in body["diseases"])


def test_wikidata_name_is_cited(client: TestClient) -> None:
    body = client.get("/structure/FMA:9999992").json()
    assert body["label_it"] == "costola"
    [cite] = [c for c in body["citations"] if c["source"] == "wikidata"]
    assert cite["url"] == "https://www.wikidata.org/wiki/Q9999999"
    assert "costola" in cite["title"]
    # senza nome italiano non c'è citazione Wikidata
    body = client.get("/structure/FMA:9999991").json()
    assert not any(c["source"] == "wikidata" for c in body["citations"])
