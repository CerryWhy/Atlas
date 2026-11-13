"""Accettazione della Fase 3: la ricerca vettoriale su 20 domande di prova restituisce
chunk pertinenti (tests/fixtures/search_queries.json, scritto prima dell'implementazione).

Gira sull'artefatto reale quando 07 ha calcolato i vettori e sentence-transformers è
installato; altrimenti viene saltato.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from api.db import connect
from api.retrieval import local
from pipeline.lib import config
from tests.pipeline_db import has_table_rows

FIXTURE = Path(__file__).parent / "fixtures" / "search_queries.json"

pytestmark = pytest.mark.skipif(
    not has_table_rows(config.DB_PATH, "embedding_meta"), reason="nessun vettore: eseguire 07"
)


def evaluate(conn: sqlite3.Connection) -> tuple[int, list[str]]:
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    passed, report = 0, []
    for item in spec["queries"]:
        hits = local.search(conn, item["q"], spec["k"])
        titles = [str(h["title"]) for h in hits]
        ok = any(want in t.lower() for t in titles for want in item["titles"])
        passed += ok
        report.append(f"{'✓' if ok else '✗'} {item['q']!r} → {titles}")
    return passed, report


def test_search_answers_the_trial_questions() -> None:
    pytest.importorskip("sentence_transformers")
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(spec["queries"]) == 20
    conn = connect(config.DB_PATH)
    try:
        passed, report = evaluate(conn)
    finally:
        conn.close()
    print("\n".join(report))
    assert passed >= spec["min_pass"], f"{passed}/20\n" + "\n".join(report)
