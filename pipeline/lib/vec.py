"""sqlite-vec: tabella virtuale degli embedding dei chunk (SPEC §4, §6).

La tabella `chunk_vec` ha chiave chunk_id e distanza coseno; `title_vec` ha un vettore
per documento, calcolato dal solo titolo: una domanda breve ("embolia polmonare")
somiglia al titolo del capitolo giusto più che a qualunque suo paragrafo.
`embedding_meta` ricorda modello e dimensione: se cambiano, i vettori vecchi non sono
confrontabili e si rifanno.
"""

import sqlite3

import sqlite_vec

META = """
CREATE TABLE IF NOT EXISTS embedding_meta (
  id    INTEGER PRIMARY KEY CHECK (id = 1),
  model TEXT NOT NULL,
  dim   INTEGER NOT NULL
);
-- il titolo da cui è stato calcolato ogni vettore di title_vec: se 05 lo cambia, si rifà
CREATE TABLE IF NOT EXISTS title_vec_src (
  doc_id TEXT PRIMARY KEY,
  title  TEXT NOT NULL
);
-- modello e dimensione dei vettori dei fenotipi (un modello diverso da embedding_meta)
CREATE TABLE IF NOT EXISTS phenotype_vec_meta (
  id    INTEGER PRIMARY KEY CHECK (id = 1),
  model TEXT NOT NULL,
  dim   INTEGER NOT NULL
);
-- il nome (nome HPO o un sinonimo) da cui è stato calcolato ogni vettore di phenotype_vec;
-- chiave '<hpo_id>#<n>', un vettore per nome
CREATE TABLE IF NOT EXISTS phenotype_vec_src (
  name_id TEXT PRIMARY KEY,
  text    TEXT NOT NULL
);
"""


def load(conn: sqlite3.Connection) -> None:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def serialize(vector: list[float]) -> bytes:
    return bytes(sqlite_vec.serialize_float32(vector))


def has_table(conn: sqlite3.Connection, name: str = "chunk_vec") -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (name,)).fetchone()
    return row is not None


def _ensure(
    conn: sqlite3.Connection, meta: str, tables: tuple[tuple[str, str], ...], model: str, dim: int
) -> bool:
    conn.executescript(META)
    row = conn.execute(f"SELECT model, dim FROM {meta} WHERE id = 1").fetchone()
    reset = row is not None and (row[0], row[1]) != (model, dim)
    for table, key in tables:
        if reset or not has_table(conn, table):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            if table in ("title_vec", "phenotype_vec"):
                conn.execute(f"DELETE FROM {table}_src")
            conn.execute(
                f"CREATE VIRTUAL TABLE {table} USING vec0("
                f"{key} TEXT PRIMARY KEY, embedding float[{dim}] distance_metric=cosine)"
            )
    conn.execute(
        f"INSERT INTO {meta} (id, model, dim) VALUES (1, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET model = excluded.model, dim = excluded.dim",
        (model, dim),
    )
    return reset


def ensure(conn: sqlite3.Connection, model: str, dim: int) -> bool:
    """Crea (o ricrea, se il modello è cambiato) le tabelle dei vettori di chunk e titoli.
    Restituisce True se i vettori esistenti sono stati buttati."""
    return _ensure(
        conn, "embedding_meta", (("chunk_vec", "chunk_id"), ("title_vec", "doc_id")), model, dim
    )


def ensure_phenotypes(conn: sqlite3.Connection, model: str, dim: int) -> bool:
    """Come ensure, per i vettori dei nomi di fenotipo (modello proprio: config.LOCATE_MODEL)."""
    return _ensure(conn, "phenotype_vec_meta", (("phenotype_vec", "name_id"),), model, dim)


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
    gone = conn.execute(
        "SELECT doc_id FROM title_vec WHERE doc_id NOT IN (SELECT doc_id FROM document)"
    ).fetchall()
    conn.executemany("DELETE FROM title_vec WHERE doc_id = ?", gone)
    conn.execute("DELETE FROM title_vec_src WHERE doc_id NOT IN (SELECT doc_id FROM document)")
    # titoli cambiati da 05: il vettore vecchio non vale più
    stale = conn.execute(
        """
        SELECT s.doc_id FROM title_vec_src s JOIN document d USING (doc_id)
        WHERE s.title <> d.title
        """
    ).fetchall()
    conn.executemany("DELETE FROM title_vec WHERE doc_id = ?", stale)
    conn.executemany("DELETE FROM title_vec_src WHERE doc_id = ?", stale)
    return len(orphans) + len(gone) + len(stale)


def titles_without_vectors(
    conn: sqlite3.Connection, limit: int, sources: set[str] | None = None
) -> list[tuple[str, str]]:
    """(doc_id, titolo) dei documenti il cui titolo non ha ancora un vettore,
    eventualmente solo delle fonti indicate."""
    where, params = "", []
    if sources:
        where = f"AND source IN ({','.join('?' * len(sources))})"
        params = sorted(sources)
    return conn.execute(
        f"""
        SELECT doc_id, title FROM document
        WHERE doc_id NOT IN (SELECT doc_id FROM title_vec) {where} ORDER BY doc_id LIMIT ?
        """,
        (*params, limit),
    ).fetchall()


def insert_titles(conn: sqlite3.Connection, rows: list[tuple[str, str, list[float]]]) -> None:
    """rows = (doc_id, titolo usato, vettore)."""
    conn.executemany(
        "INSERT INTO title_vec (doc_id, embedding) VALUES (?, ?)",
        [(doc_id, serialize(v)) for doc_id, _t, v in rows],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO title_vec_src (doc_id, title) VALUES (?, ?)",
        [(doc_id, title) for doc_id, title, _v in rows],
    )


def insert(conn: sqlite3.Connection, rows: list[tuple[str, list[float]]]) -> None:
    conn.executemany(
        "INSERT INTO chunk_vec (chunk_id, embedding) VALUES (?, ?)",
        [(cid, serialize(v)) for cid, v in rows],
    )


def phenotypes_to_refresh(
    conn: sqlite3.Connection, wanted: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Dei nomi di fenotipo da indicizzare (name_id, nome), quelli senza vettore o con un
    nome cambiato; toglie i vettori dei nomi non più indicizzati o cambiati."""
    have = dict(conn.execute("SELECT name_id, text FROM phenotype_vec_src").fetchall())
    want = dict(wanted)
    stale = [h for h, t in have.items() if want.get(h) != t]
    conn.executemany("DELETE FROM phenotype_vec WHERE name_id = ?", [(h,) for h in stale])
    conn.executemany("DELETE FROM phenotype_vec_src WHERE name_id = ?", [(h,) for h in stale])
    return [(h, t) for h, t in wanted if have.get(h) != t]


def insert_phenotypes(conn: sqlite3.Connection, rows: list[tuple[str, str, list[float]]]) -> None:
    """rows = (name_id, nome usato, vettore)."""
    conn.executemany(
        "INSERT INTO phenotype_vec (name_id, embedding) VALUES (?, ?)",
        [(h, serialize(v)) for h, _t, v in rows],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO phenotype_vec_src (name_id, text) VALUES (?, ?)",
        [(h, t) for h, t, _v in rows],
    )
