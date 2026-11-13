"""Test dell'API sull'artefatto reale: richiedono la pipeline eseguita."""

import pytest
from fastapi.testclient import TestClient

from api.db import DB_PATH
from api.main import app
from tests.pipeline_db import has_table_rows

pytestmark = pytest.mark.skipif(
    not has_table_rows(DB_PATH, "structure"), reason="atlas.db non generato (o senza strutture)"
)
client = TestClient(app)


def test_liver_has_real_diseases_with_icd11() -> None:
    r = client.get("/structure/FMA:7197")
    assert r.status_code == 200
    body = r.json()
    assert body["fma_id"] == "FMA:7197"
    assert body["uberon_id"] == "UBERON:0002107"
    assert body["radius"] > 0 and body["centroid"] is not None
    assert len(body["diseases"]) >= 3
    assert any(d["icd11_code"] for d in body["diseases"])
    for item in [*body["diseases"], *body["phenotypes"]]:
        assert item["citations"], "I2: ogni voce clinica deve portare una fonte"
        assert all(c["license"] and c["url"].startswith("http") for c in item["citations"])


def test_liver_hierarchy_and_highlight_nodes() -> None:
    body = client.get("/structure/FMA:7197").json()
    assert body["ancestors"], "il fegato ha antenati part_of"
    assert body["ancestors"][-1]["fma_id"] == body["parent_fma_id"]
    assert len(body["children"]) >= 2
    # il fegato non ha un nodo proprio: si accende tramite le sue parti
    assert body["mesh_node"] is None
    assert len(body["mesh_nodes"]) >= 5
    assert all(n.startswith("FMA:") for n in body["mesh_nodes"])


def test_region_nodes_resolve_to_a_focus_structure() -> None:
    regions = client.get("/regions").json()
    assert len(regions) >= 2
    assert "abdomen.glb" in {r["mesh_file"] for r in regions}
    seen: set[str] = set()
    for region in regions:
        nodes = client.get(f"/regions/{region['mesh_file']}/nodes").json()
        assert len(nodes) == region["structures"]
        ids = {n["fma_id"] for n in nodes}
        assert len(ids) == len(nodes) and not (ids & seen), "un nodo sta in un solo GLB"
        seen |= ids
        for n in nodes[:10]:
            assert client.get(f"/structure/{n['focus_fma_id']}").status_code == 200


def test_sided_structure_inherits_and_says_so() -> None:
    """Right humerus non ha un termine UBERON proprio: eredita da Humerus, dichiarandolo."""
    body = client.get("/structure/FMA:23130").json()
    assert body["label_en"] == "Right humerus"
    assert body["uberon_id"] is None, "uberon_id resta solo l'xref esatto"
    assert body["inherited_from"], "deve dichiarare da dove eredita"
    link = body["inherited_from"][0]
    assert link["unsided_label"] == "Humerus"
    assert {c["source"] for c in link["citations"]} >= {"fma", "uberon"}
    items = [*body["diseases"], *body["phenotypes"]]
    assert items and all(i["inherited"] for i in items)
    # I2: ogni voce ereditata cita chi asserisce la sede E la relazione di lato
    for item in items:
        sources = [c["source"] for c in item["citations"]]
        assert sources[0] in {"mondo", "doid", "hpo"}
        assert any(c["title"].startswith("FMA: Right humerus") for c in item["citations"])


def test_note_cites_the_link_that_carries_content() -> None:
    """Right kidney eredita due termini: solo "kidney" porta malattie e segni."""
    body = client.get("/structure/FMA:7204").json()
    carrying = [link for link in body["inherited_from"] if link["carries_content"]]
    assert [link["unsided_label"] for link in carrying] == ["kidney"]
    assert all(not link["unsided_label"].startswith("UBERON:") for link in body["inherited_from"])


def test_exact_content_is_not_marked_inherited() -> None:
    body = client.get("/structure/FMA:7197").json()  # fegato: legame esatto
    assert body["inherited_from"] == []
    assert body["diseases"] and not any(d["inherited"] for d in body["diseases"])


def test_free_text_ids_are_rejected() -> None:
    assert client.get("/structure/liver").status_code == 422
    assert client.get("/regions/ATLAS.DB/nodes").status_code == 422


def test_unknown_structure_is_404() -> None:
    assert client.get("/structure/FMA:1").status_code == 404
    assert client.get("/regions/pancreas.glb/nodes").status_code == 404


def test_attribution_includes_bodyparts3d() -> None:
    rows = client.get("/attribution").json()
    bp = next(r for r in rows if r["source"] == "bodyparts3d")
    assert "The Database Center for Life Science" in bp["attribution"]
    assert all(r["license"] for r in rows)


def test_mesh_is_served() -> None:
    r = client.get("/meshes/abdomen.glb")
    assert r.status_code == 200
    assert r.content[:4] == b"glTF"
