"""Accettazione della Fase 3 (SPEC §10) sull'artefatto reale.

Girano se 05 è stato eseguito; quelli che usano le strutture richiedono anche 03/04.
"""

import sqlite3
from collections.abc import Iterator

import pytest

from pipeline.lib import config, docsrc
from tests.pipeline_db import has_table_rows

pytestmark = pytest.mark.skipif(
    not has_table_rows(config.DB_PATH, "document"), reason="nessun documento: eseguire 05"
)
needs_structures = pytest.mark.skipif(
    not has_table_rows(config.DB_PATH, "structure"), reason="strutture assenti: eseguire 03/04"
)
KNOWN_LICENSES = {*docsrc.LICENSE_NAMES.values(), docsrc.MEDLINEPLUS_LICENSE}


@pytest.fixture(scope="module")
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(f"{config.DB_PATH.as_uri()}?mode=ro", uri=True)
    yield c
    c.close()


def rows(conn: sqlite3.Connection, sql: str) -> list[tuple[object, ...]]:
    return conn.execute(sql).fetchall()


def test_no_document_without_a_known_license(conn: sqlite3.Connection) -> None:
    """I3: zero righe con licenza vuota o segnaposto."""
    licenses = {r[0] for r in rows(conn, "SELECT DISTINCT license FROM document")}
    assert licenses <= KNOWN_LICENSES, licenses - KNOWN_LICENSES


def test_every_source_is_loaded_and_registered(conn: sqlite3.Connection) -> None:
    counts = dict(rows(conn, "SELECT source, COUNT(*) FROM document GROUP BY source"))
    assert counts.get("medlineplus", 0) > 500
    assert counts.get("orphanet", 0) > 5000
    assert counts.get("statpearls", 0) > 5000
    registered = {r[0] for r in rows(conn, "SELECT source FROM source_release")}
    assert set(counts) <= registered, "ogni fonte di documenti va in /attribution"


def test_documents_open_at_their_source(conn: sqlite3.Connection) -> None:
    bad = rows(
        conn,
        """
        SELECT doc_id, url FROM document WHERE NOT (
          (source = 'statpearls' AND url LIKE 'https://www.ncbi.nlm.nih.gov/books/n/statpearls/%')
          OR (source = 'orphanet' AND url LIKE 'https://www.orpha.net/%')
          OR (source = 'medlineplus' AND url LIKE 'https://medlineplus.gov/%')
        ) LIMIT 5
        """,
    )
    assert bad == []


def test_links_say_how_they_were_made(conn: sqlite3.Connection) -> None:
    """I2: ogni legame documento → malattia/struttura dichiara basis e via."""
    for table in ("document_disease", "document_structure"):
        missing = rows(conn, f"SELECT COUNT(*) FROM {table} WHERE basis IS NULL OR via IS NULL")
        assert missing == [(0,)], table


def test_bibliography_markers_are_stripped(conn: sqlite3.Connection) -> None:
    """Nella Fase 4 i marcatori [n] sono delle citazioni dell'assistente."""
    marked = rows(
        conn,
        "SELECT COUNT(*) FROM document WHERE source = 'statpearls' AND text GLOB '*[[][0-9]]*'",
    )
    assert marked[0][0] < 50  # qualche [n] può restare dentro tabelle o formule


@needs_structures
def test_every_abdominal_structure_with_uberon_has_a_document(conn: sqlite3.Connection) -> None:
    """Accettazione Fase 3: ogni struttura addominale con uberon_id ha ≥ 1 documento."""
    missing = rows(
        conn,
        """
        SELECT s.fma_id, s.label_en FROM structure s
        WHERE s.region = 'abdomen' AND s.uberon_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM document_structure ds WHERE ds.fma_id = s.fma_id)
        """,
    )
    assert missing == [], f"{len(missing)} strutture senza documenti, es. {missing[:5]}"
