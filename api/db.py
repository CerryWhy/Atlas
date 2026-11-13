"""Connessione in sola lettura all'artefatto della pipeline (I6).

Carica l'estensione sqlite-vec (Fase 3) per la ricerca sui vettori dei chunk.
"""

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import sqlite_vec

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("ATLAS_DB", ROOT / "data" / "atlas.db"))
MESHES_DIR = Path(os.environ.get("ATLAS_MESHES", ROOT / "data" / "meshes"))


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"{path} non esiste: eseguire prima la pipeline")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
