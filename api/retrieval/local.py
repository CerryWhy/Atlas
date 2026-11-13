"""Tier 1 (SPEC §8): ricerca vettoriale sul corpus curato locale.

La domanda si codifica con lo STESSO modello usato da 07 per i chunk (letto da
embedding_meta), in locale: nessun testo esce dalla macchina (SPEC §4).
"""

import sqlite3
from functools import lru_cache
from typing import Any

import sqlite_vec

from api import queries


class SearchUnavailable(RuntimeError):
    """Mancano i vettori (07 non eseguito) o le dipendenze per gli embedding."""


@lru_cache(maxsize=2)
def _model(name: str) -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise SearchUnavailable('manca sentence-transformers: pip install -e ".[embed]"') from e
    return SentenceTransformer(name)


def encode_query(conn: sqlite3.Connection, text: str) -> bytes:
    name = queries.embedding_model(conn)
    if name is None:
        raise SearchUnavailable("nessun vettore in atlas.db: eseguire pipeline/07_embed")
    vector = _model(name).encode([f"query: {text}"], normalize_embeddings=True)[0]
    return bytes(sqlite_vec.serialize_float32(vector.tolist()))


def search(conn: sqlite3.Connection, text: str, k: int) -> list[sqlite3.Row]:
    return queries.nearest_chunks(conn, encode_query(conn, text), k)
