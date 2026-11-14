"""Tier 1 (SPEC §8): ricerca vettoriale sul corpus curato locale.

La domanda si codifica con lo STESSO modello usato da 07 per i chunk (letto da
embedding_meta), in locale: nessun testo esce dalla macchina (SPEC §4).

Si cercano insieme i chunk e i titoli dei documenti, e si restituisce UN risultato per
documento: senza questo, cinque paragrafi dello stesso capitolo occupano tutti i primi
posti, e il capitolo il cui titolo È la domanda ("Pulmonary Embolism") resta dietro a
paragrafi che la nominano soltanto.

Le due liste si fondono per POSIZIONE (Reciprocal Rank Fusion), non per distanza: le
distanze di un titolo di cinque parole e di un paragrafo di trecento non sono
confrontabili (sui dati reali i titoli risultavano sempre più vicini, e i paragrafi non
contavano più). Un documento presente in entrambe le liste sale; uno trovato solo dal
titolo si presenta con il suo primo chunk.
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
RRF_K = 60  # costante standard della Reciprocal Rank Fusion (Cormack et al., 2009)

Hit = tuple[str, str, float]  # (chunk_id, doc_id, distance)


def best_per_document(hits: list[Hit]) -> list[Hit]:
    """Un risultato per documento, il più vicino; in ordine di distanza."""
    best: dict[str, Hit] = {}
    for hit in sorted(hits, key=lambda h: (h[2], h[0])):
        best.setdefault(hit[1], hit)
    return sorted(best.values(), key=lambda h: (h[2], h[0]))


def fuse(chunk_hits: list[Hit], title_hits: list[Hit], k: int) -> list[Hit]:
    """I k documenti con il punteggio RRF più alto: somma di 1 / (RRF_K + posizione) su
    ciascuna lista in cui il documento compare. Il chunk mostrato è il paragrafo trovato
    se c'è, altrimenti il primo chunk del documento trovato dal titolo; la distanza è
    quella di quel chunk o titolo. A parità di punteggio, il doc_id minore."""
    score: dict[str, float] = {}
    shown: dict[str, Hit] = {}
    for ranked in (best_per_document(chunk_hits), best_per_document(title_hits)):
        for rank, hit in enumerate(ranked, start=1):
            score[hit[1]] = score.get(hit[1], 0.0) + 1.0 / (RRF_K + rank)
            shown.setdefault(hit[1], hit)  # i chunk vengono prima dei titoli
    order = sorted(score, key=lambda d: (-score[d], d))
    return [shown[d] for d in order[:k]]


def search(conn: sqlite3.Connection, text: str, k: int) -> list[dict[str, Any]]:
    query = encode_query(conn, text)
    n = k * OVERSAMPLE
    top = fuse(
        queries.nearest_chunk_ids(conn, query, n),
        queries.nearest_title_docs(conn, query, n),
        k,
    )
    if not top:
        return []
    rows = {r["chunk_id"]: r for r in queries.chunks_with_documents(conn, [t[0] for t in top])}
    return [{**dict(rows[cid]), "distance": dist} for cid, _doc, dist in top if cid in rows]
