"""Test sui dati, non solo sul codice (SPEC §11)."""

import sqlite3
from pathlib import Path

import pytest

from pipeline.lib import db


def test_document_license_cannot_be_empty(tmp_path: Path) -> None:
    """I3: document.license è NOT NULL e non può essere vuota."""
    conn = db.connect(tmp_path / "t.db")
    db.migrate(conn)
    row = ("d1", "medlineplus", "t", "http://x", "2026-01-01", "body")
    for bad in (None, "", "   "):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO document (doc_id, source, title, url, retrieved, text, license) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (*row, bad),
            )


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.migrate(conn)
    db.migrate(conn)


def test_old_structure_uberon_accepts_is_a_links_after_migrate(tmp_path: Path) -> None:
    """Un database creato prima di 'fma_is_a' ha un CHECK che lo rifiuta: migrate lo
    ricrea, e la tabella torna a rifiutare le provenienze sconosciute."""
    conn = db.connect(tmp_path / "t.db")
    conn.execute(
        "CREATE TABLE structure_uberon (fma_id TEXT NOT NULL, uberon_id TEXT NOT NULL,"
        " basis TEXT NOT NULL CHECK (basis IN ('xref', 'fma_laterality', 'uberon_laterality')),"
        " via_id TEXT, via_label TEXT, PRIMARY KEY (fma_id, uberon_id))"
    )
    db.migrate(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    db.replace_structure_uberon(
        conn, [("FMA:1", "UBERON:0002228", "fma_is_a", "FMA:3", "Rib", "Rib")]
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.replace_structure_uberon(conn, [("FMA:1", "UBERON:1", "guess", "FMA:3", "x", "x")])
    with pytest.raises(sqlite3.IntegrityError):  # un legame ereditato dichiara da dove viene
        db.replace_structure_uberon(conn, [("FMA:1", "UBERON:1", "fma_is_a", None, None, None)])
