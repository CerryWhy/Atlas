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
        ORDER BY d.icd11_code IS NULL, d.label
        """,
        (fma_id,),
    ).fetchall()


def phenotypes_for_structure(conn: sqlite3.Connection, fma_id: str) -> list[sqlite3.Row]:
    """Fenotipi HPO la cui definizione logica ha sede nella struttura (ponte UBERON)."""
    return conn.execute(
        """
        SELECT p.hpo_id, p.label
        FROM structure s
        JOIN phenotype_structure ps ON ps.uberon_id = s.uberon_id
        JOIN phenotype p ON p.hpo_id = ps.hpo_id
        WHERE s.fma_id = ?
        ORDER BY p.label
        """,
        (fma_id,),
    ).fetchall()


def ancestors(conn: sqlite3.Connection, fma_id: str) -> list[sqlite3.Row]:
    """Catena part_of dalla radice fino al genitore (esclusa la struttura stessa)."""
    return conn.execute(
        """
        WITH RECURSIVE up(fma_id, parent_fma_id, hops) AS (
          SELECT fma_id, parent_fma_id, 0 FROM structure WHERE fma_id = ?
          UNION ALL
          SELECT s.fma_id, s.parent_fma_id, u.hops + 1
          FROM structure s JOIN up u ON s.fma_id = u.parent_fma_id
        )
        SELECT s.fma_id, s.label_en, s.label_it
        FROM up JOIN structure s ON s.fma_id = up.fma_id
        WHERE up.hops > 0 ORDER BY up.hops DESC
        """,
        (fma_id,),
    ).fetchall()


def children(conn: sqlite3.Connection, fma_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT fma_id, label_en, label_it, uberon_id IS NOT NULL AS has_uberon
        FROM structure WHERE parent_fma_id = ? ORDER BY label_en
        """,
        (fma_id,),
    ).fetchall()


_DESCEND = """
    WITH RECURSIVE descend(fma_id) AS (
      SELECT fma_id FROM structure WHERE fma_id = ?
      UNION ALL
      SELECT s.fma_id FROM structure s JOIN descend d ON s.parent_fma_id = d.fma_id
    )
"""


def mesh_nodes_under(conn: sqlite3.Connection, fma_id: str) -> list[str]:
    """Nodi GLB della struttura e di tutte le sue parti: ciò che la scena deve accendere."""
    rows = conn.execute(
        _DESCEND
        + """
        SELECT s.mesh_node FROM descend d JOIN structure s ON s.fma_id = d.fma_id
        WHERE s.mesh_node IS NOT NULL ORDER BY s.mesh_node
        """,
        (fma_id,),
    ).fetchall()
    return [r[0] for r in rows]


def mesh_nodes(conn: sqlite3.Connection, mesh_file: str) -> list[sqlite3.Row]:
    """Ogni nodo di un GLB con la sua struttura 'di fuoco': la più vicina, risalendo
    part_of, che abbia un uberon_id (cioè sapere clinico collegato); altrimenti sé stessa.
    Non si risale fino ai sistemi (depth < 3): sarebbe un fuoco troppo largo per un click."""
    return conn.execute(
        """
        WITH RECURSIVE up(node, fma_id, hops) AS (
          SELECT fma_id, fma_id, 0 FROM structure WHERE mesh_file = ?
          UNION ALL
          SELECT u.node, s.parent_fma_id, u.hops + 1
          FROM up u JOIN structure s ON s.fma_id = u.fma_id
          WHERE s.uberon_id IS NULL AND s.parent_fma_id IS NOT NULL
        ),
        nearest AS (
          SELECT u.node, u.fma_id, MAX(u.hops) AS hops
          FROM up u JOIN structure s ON s.fma_id = u.fma_id
          WHERE s.uberon_id IS NOT NULL AND s.depth >= 3 GROUP BY u.node
        )
        SELECT n.fma_id, n.label_en, n.label_la, n.label_it, n.system,
               f.fma_id AS focus_fma_id, f.label_en AS focus_label_en,
               f.label_it AS focus_label_it
        FROM structure n
        LEFT JOIN nearest ON nearest.node = n.fma_id
        JOIN structure f ON f.fma_id = COALESCE(nearest.fma_id, n.fma_id)
        WHERE n.mesh_file = ? ORDER BY n.fma_id
        """,
        (mesh_file, mesh_file),
    ).fetchall()


def mesh_files(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """GLB disponibili: l'app li scopre da qui (nessun file cablato nel frontend)."""
    # la regione di un file è quella della maggioranza dei suoi nodi
    return conn.execute(
        """
        WITH c AS (
          SELECT mesh_file, region, COUNT(*) AS n
          FROM structure WHERE mesh_file IS NOT NULL GROUP BY mesh_file, region
        )
        SELECT mesh_file,
               (SELECT c2.region FROM c c2 WHERE c2.mesh_file = c.mesh_file
                ORDER BY c2.region IS NULL, c2.n DESC, c2.region LIMIT 1) AS region,
               SUM(n) AS structures
        FROM c GROUP BY mesh_file ORDER BY mesh_file
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
