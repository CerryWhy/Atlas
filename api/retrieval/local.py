"""Tier 1 (SPEC §8): ricerca vettoriale sul corpus curato locale.

La domanda si codifica con lo STESSO modello usato da 07 per i chunk (letto da
embedding_meta), in locale: nessun testo esce dalla macchina (SPEC §4).

Si cercano insieme i chunk e i titoli dei documenti, e si restituisce UN risultato per
documento (il suo punto più vicino alla domanda): senza questo, cinque paragrafi dello
stesso capitolo occupano tutti i primi posti, e il capitolo il cui titolo È la domanda
("Pulmonary Embolism") resta dietro a paragrafi che la nominano soltanto. Un documento
trovato dal titolo si presenta con il suo primo chunk.
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


OVERSAMPLE = 6  # vicini chiesti per ogni risultato voluto, prima di unire per documento


def merge_by_document(hits: list[tuple[str, str, float]], k: int) -> list[tuple[str, str, float]]:
    """Da (chunk_id, doc_id, distance) ai k documenti più vicini, uno per documento:
    resta il chunk con la distanza minore (a parità, il chunk_id minore)."""
    best: dict[str, tuple[str, str, float]] = {}
    for chunk_id, doc_id, distance in sorted(hits, key=lambda h: (h[2], h[0])):
        best.setdefault(doc_id, (chunk_id, doc_id, distance))
    return sorted(best.values(), key=lambda h: (h[2], h[0]))[:k]


def search(conn: sqlite3.Connection, text: str, k: int) -> list[dict[str, Any]]:
    query = encode_query(conn, text)
    n = k * OVERSAMPLE
    found = [
        (str(r["chunk_id"]), str(r["doc_id"]), float(r["distance"]))
        for r in (
            *queries.nearest_chunk_ids(conn, query, n),
            *queries.nearest_title_docs(conn, query, n),
        )
    ]
    top = merge_by_document(found, k)
    if not top:
        return []
    rows = {r["chunk_id"]: r for r in queries.chunks_with_documents(conn, [t[0] for t in top])}
    return [{**dict(rows[cid]), "distance": dist} for cid, _doc, dist in top if cid in rows]
