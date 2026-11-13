"""sqlite-vec: tabella virtuale degli embedding dei chunk (SPEC §4, §6).

La tabella `chunk_vec` ha chiave chunk_id e distanza coseno. `embedding_meta` ricorda
modello e dimensione: se cambiano, i vettori vecchi non sono confrontabili e si rifanno.
"""

import sqlite3

import sqlite_vec

META = """
CREATE TABLE IF NOT EXISTS embedding_meta (
  id    INTEGER PRIMARY KEY CHECK (id = 1),
  model TEXT NOT NULL,
  dim   INTEGER NOT NULL
);
"""


def load(conn: sqlite3.Connection) -> None:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def serialize(vector: list[float]) -> bytes:
    return bytes(sqlite_vec.serialize_float32(vector))


def has_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'chunk_vec'").fetchone()
    return row is not None


def ensure(conn: sqlite3.Connection, model: str, dim: int) -> bool:
    """Crea (o ricrea, se il modello è cambiato) la tabella dei vettori.
    Restituisce True se i vettori esistenti sono stati buttati."""
    conn.executescript(META)
    row = conn.execute("SELECT model, dim FROM embedding_meta WHERE id = 1").fetchone()
    reset = row is not None and (row[0], row[1]) != (model, dim)
    if reset or not has_table(conn):
        conn.execute("DROP TABLE IF EXISTS chunk_vec")
        conn.execute(
            f"CREATE VIRTUAL TABLE chunk_vec USING vec0("
            f"chunk_id TEXT PRIMARY KEY, embedding float[{dim}] distance_metric=cosine)"
        )
    conn.execute(
        "INSERT INTO embedding_meta (id, model, dim) VALUES (1, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET model = excluded.model, dim = excluded.dim",
        (model, dim),
    )
    return reset


def chunks_without_vectors(
    conn: sqlite3.Connection,
    limit: int,
    sources: set[str] | None = None,
    first_chunks: int = 0,
) -> list[tuple[str, str, str]]:
    """(chunk_id, titolo del documento, testo) dei chunk ancora senza vettore,
    eventualmente solo delle fonti indicate o dei primi `first_chunks` di ogni documento."""
    where = ""
    params: list[object] = []
    if sources:
        where += f" AND d.source IN ({','.join('?' * len(sources))})"
        params += sorted(sources)
    if first_chunks:
        where += " AND c.ordinal < ?"
        params.append(first_chunks)
    return conn.execute(
        f"""
        SELECT c.chunk_id, d.title, c.text FROM chunk c JOIN document d USING (doc_id)
        WHERE c.chunk_id NOT IN (SELECT chunk_id FROM chunk_vec) {where}
        ORDER BY c.chunk_id LIMIT ?
        """,
        (*params, limit),
    ).fetchall()


def missing_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM chunk WHERE chunk_id NOT IN (SELECT chunk_id FROM chunk_vec)"
    ).fetchone()
    return int(row[0])


def delete_orphans(conn: sqlite3.Connection) -> int:
    orphans = conn.execute(
        "SELECT chunk_id FROM chunk_vec WHERE chunk_id NOT IN (SELECT chunk_id FROM chunk)"
    ).fetchall()
    conn.executemany("DELETE FROM chunk_vec WHERE chunk_id = ?", orphans)
    return len(orphans)


def insert(conn: sqlite3.Connection, rows: list[tuple[str, list[float]]]) -> None:
    conn.executemany(
        "INSERT INTO chunk_vec (chunk_id, embedding) VALUES (?, ?)",
        [(cid, serialize(v)) for cid, v in rows],
    )
