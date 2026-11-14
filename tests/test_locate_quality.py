"""Accettazione della Fase 5 (SPEC §10): su 20 sintomi in italiano colloquiale
(tests/fixtures/symptoms.json, scritto prima dell'implementazione) almeno 16 portano
alla struttura giusta tra le prime 5. Gira sull'artefatto reale quando 07 ha
indicizzato i fenotipi e sentence-transformers è installato."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from pipeline.lib import config
from tests.pipeline_db import has_table_rows

FIXTURE = Path(__file__).parent / "fixtures" / "symptoms.json"

pytestmark = pytest.mark.skipif(
    not has_table_rows(config.DB_PATH, "phenotype_vec_meta"),
    reason="fenotipi non indicizzati: eseguire 04 e 07",
)


def test_symptoms_lead_to_the_right_structures() -> None:
    pytest.importorskip("sentence_transformers")
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(spec["symptoms"]) == 20
    client = TestClient(app)
    passed, report = 0, []
    for item in spec["symptoms"]:
        body = client.post("/locate", json={"text": item["q"]}).json()
        labels = [s["label_en"] for s in body["structures"][: spec["k"]]]
        ok = any(want in label.lower() for label in labels for want in item["structures"])
        passed += ok
        report.append(f"{'✓' if ok else '✗'} {item['q']!r} → {labels}")
    print("\n".join(report))
    assert passed >= spec["min_pass"], f"{passed}/20\n" + "\n".join(report)
