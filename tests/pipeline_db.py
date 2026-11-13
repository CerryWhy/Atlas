"""Quando ha senso eseguire i test sull'artefatto reale della pipeline."""

import sqlite3
from pathlib import Path


def has_table_rows(path: Path, table: str) -> bool:
    """True se atlas.db esiste e la tabella ha righe (una pipeline eseguita solo in
    parte, es. solo 05, lascia vuote le altre)."""
    if not path.exists():
        return False
    try:
        with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as conn:
            return conn.execute(f"SELECT EXISTS (SELECT 1 FROM {table})").fetchone()[0] == 1
    except sqlite3.Error:
        return False
