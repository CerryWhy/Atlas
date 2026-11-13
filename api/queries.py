"""Tutto l'SQL dell'API vive qui (SPEC §11). Nessuna query inline nelle route."""

import sqlite3


def get_structure(conn: sqlite3.Connection, fma_id: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        """
        SELECT fma_id, label_en, label_la, label_it, uberon_id, parent_fma_id,
               system, region, depth, mesh_file, mesh_node, cx, cy, cz, radius
        FROM structure WHERE fma_id = ?
        """,
        (fma_id,),
    ).fetchone()
    return row


def diseases_for_structure(conn: sqlite3.Connection, fma_id: str) -> list[sqlite3.Row]:
    """Malattie con sede anatomica = la struttura, via il ponte UBERON."""
    return conn.execute(
        """
        SELECT d.mondo_id, d.label, d.icd11_code, d.definition
        FROM structure s
        JOIN disease_structure ds ON ds.uberon_id = s.uberon_id
        JOIN disease d ON d.mondo_id = ds.mondo_id
        WHERE s.fma_id = ?
        ORDER BY d.label
        """,
        (fma_id,),
    ).fetchall()


def mesh_files(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """GLB disponibili, per regione: l'app li scopre da qui (nessun file cablato nel frontend)."""
    return conn.execute(
        """
        SELECT mesh_file, region, COUNT(*) AS structures
        FROM structure WHERE mesh_file IS NOT NULL
        GROUP BY mesh_file, region ORDER BY region, mesh_file
        """
    ).fetchall()


def source_releases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT source, title, version, url, license, attribution FROM source_release "
        "ORDER BY source"
    ).fetchall()


def source_release(conn: sqlite3.Connection, source: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT source, title, version, url, license, attribution FROM source_release "
        "WHERE source = ?",
        (source,),
    ).fetchone()
    return row
