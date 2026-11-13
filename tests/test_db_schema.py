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
