"""Tutto l'SQL dell'API vive qui (SPEC §11). Nessuna query inline nelle route."""

import sqlite3


def get_structure(conn: sqlite3.Connection, fma_id: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        """
        SELECT fma_id, label_en, label_la, label_it, label_it_source, label_it_ref,
               uberon_id, parent_fma_id,
               system, region, depth, mesh_file, mesh_node, cx, cy, cz, radius
        FROM structure WHERE fma_id = ?
        """,
        (fma_id,),
    ).fetchone()
    return row


def diseases_for_structure(conn: sqlite3.Connection, fma_id: str) -> list[sqlite3.Row]:
    """Malattie con sede nella struttura, una riga per percorso: legame UBERON usato
    (esatto o ereditato dalla versione senza lato) e fonte che asserisce la sede
    (`site_source` 'mondo' | 'doid', `site_source_id`). Le righe di un percorso esatto
    vengono prima."""
    return conn.execute(
        """
        SELECT d.mondo_id, d.label, d.icd11_code, su.basis, su.uberon_id,
               ds.source AS site_source, ds.source_id AS site_source_id
        FROM structure_uberon su
        JOIN disease_structure ds ON ds.uberon_id = su.uberon_id
        JOIN disease d ON d.mondo_id = ds.mondo_id
        WHERE su.fma_id = ?
        ORDER BY d.icd11_code IS NULL, d.label, d.mondo_id, su.basis <> 'xref', su.uberon_id
        """,
        (fma_id,),
    ).fetchall()


def phenotypes_for_structure(conn: sqlite3.Connection, fma_id: str) -> list[sqlite3.Row]:
    """Fenotipi HPO la cui definizione logica ha sede nella struttura, una riga per
    percorso (legame esatto prima). Un fenotipo bilaterale non vale per una struttura
    con un solo lato (lo marcano entrambi la pipeline: phenotype.bilateral, structure.sided)."""
    return conn.execute(
        """
        SELECT p.hpo_id, p.label, su.basis, su.uberon_id
        FROM structure_uberon su
        JOIN structure s ON s.fma_id = su.fma_id
        JOIN phenotype_structure ps ON ps.uberon_id = su.uberon_id
        JOIN phenotype p ON p.hpo_id = ps.hpo_id
        WHERE su.fma_id = ? AND NOT (s.sided = 1 AND p.bilateral = 1)
        ORDER BY p.label, p.hpo_id, su.basis <> 'xref', su.uberon_id
        """,
        (fma_id,),
    ).fetchall()


def inherited_links(conn: sqlite3.Connection, fma_id: str) -> list[sqlite3.Row]:
    """Legami UBERON ereditati dalla versione senza lato, con la loro provenienza."""
    return conn.execute(
        """
        SELECT su.uberon_id, su.basis, su.via_id, su.via_label, su.unsided_label,
               EXISTS (SELECT 1 FROM disease_structure ds WHERE ds.uberon_id = su.uberon_id)
               OR EXISTS (
                 SELECT 1 FROM phenotype_structure ps JOIN phenotype p ON p.hpo_id = ps.hpo_id
                 WHERE ps.uberon_id = su.uberon_id AND NOT (s.sided = 1 AND p.bilateral = 1)
               ) AS carries_content
        FROM structure_uberon su JOIN structure s ON s.fma_id = su.fma_id
        WHERE su.fma_id = ? AND su.basis <> 'xref' ORDER BY su.uberon_id
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
        SELECT s.fma_id, s.label_en, s.label_it,
               EXISTS (SELECT 1 FROM structure_uberon su WHERE su.fma_id = s.fma_id)
                 AS has_uberon
        FROM structure s WHERE s.parent_fma_id = ? ORDER BY s.label_en
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
    part_of, che abbia un legame UBERON (esatto o ereditato dalla versione senza lato);
    altrimenti sé stessa.
    Non si risale fino ai sistemi (depth < 3): sarebbe un fuoco troppo largo per un click."""
    return conn.execute(
        """
        WITH RECURSIVE up(node, fma_id, hops) AS (
          SELECT fma_id, fma_id, 0 FROM structure WHERE mesh_file = ?
          UNION ALL
          SELECT u.node, s.parent_fma_id, u.hops + 1
          FROM up u JOIN structure s ON s.fma_id = u.fma_id
          WHERE s.parent_fma_id IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM structure_uberon su WHERE su.fma_id = s.fma_id)
        ),
        nearest AS (
          SELECT u.node, u.fma_id, MAX(u.hops) AS hops
          FROM up u JOIN structure s ON s.fma_id = u.fma_id
          WHERE s.depth >= 3
            AND EXISTS (SELECT 1 FROM structure_uberon su WHERE su.fma_id = s.fma_id)
          GROUP BY u.node
        )
        SELECT n.fma_id, n.label_en, n.label_la, n.label_it, n.system, n.tissue,
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
