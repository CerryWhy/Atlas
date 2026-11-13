"""Test di Fase 0 sull'artefatto reale: richiedono `npm run pipeline:phase0`."""

import pytest
from fastapi.testclient import TestClient

from api.db import DB_PATH
from api.main import app

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="atlas.db non generato")
client = TestClient(app)


def test_liver_has_real_diseases_with_icd11() -> None:
    r = client.get("/structure/FMA:7197")
    assert r.status_code == 200
    body = r.json()
    assert body["fma_id"] == "FMA:7197"
    assert body["uberon_id"] == "UBERON:0002107"
    assert body["radius"] > 0 and body["centroid"] is not None
    assert len(body["diseases"]) >= 3
    for d in body["diseases"]:
        assert d["mondo_id"].startswith("MONDO:")
        assert d["icd11_code"]
        assert d["citations"], "I2: ogni malattia deve portare una fonte"
        assert all(c["license"] and c["url"].startswith("http") for c in d["citations"])


def test_free_text_ids_are_rejected() -> None:
    assert client.get("/structure/liver").status_code == 422


def test_unknown_structure_is_404() -> None:
    assert client.get("/structure/FMA:1").status_code == 404


def test_attribution_includes_bodyparts3d() -> None:
    rows = client.get("/attribution").json()
    bp = next(r for r in rows if r["source"] == "bodyparts3d")
    assert "The Database Center for Life Science" in bp["attribution"]
    assert all(r["license"] for r in rows)


def test_mesh_is_served() -> None:
    r = client.get("/meshes/liver.glb")
    assert r.status_code == 200
    assert r.content[:4] == b"glTF"
