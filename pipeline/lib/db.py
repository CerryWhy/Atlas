"""Schema di atlas.db (SPEC §6) e helper di connessione per la pipeline.

Tutto l'SQL di scrittura della pipeline vive qui (SPEC §11).
La tabella virtuale sqlite-vec per gli embedding arriva in Fase 3.
"""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS structure (
  fma_id        TEXT PRIMARY KEY,
  label_en      TEXT NOT NULL,
  label_la      TEXT,
  label_it      TEXT,
  uberon_id     TEXT,
  parent_fma_id TEXT REFERENCES structure(fma_id),
  system        TEXT,
  region        TEXT,
  depth         INTEGER NOT NULL DEFAULT 0,
  mesh_file     TEXT,
  mesh_node     TEXT,
  cx REAL, cy REAL, cz REAL,
  radius        REAL
);
CREATE INDEX IF NOT EXISTS idx_structure_parent ON structure(parent_fma_id);
CREATE INDEX IF NOT EXISTS idx_structure_uberon ON structure(uberon_id);
CREATE INDEX IF NOT EXISTS idx_structure_region ON structure(region);

-- Estensione allo schema di SPEC §6: i legami struttura → UBERON con la loro
-- provenienza. `structure.uberon_id` resta solo il crosswalk esatto; qui ci sono anche
-- i legami ereditati dalla versione senza lato (vedi pipeline/lib/laterality.py).
--   basis = 'xref'              xref FMA esatto sul termine UBERON (= structure.uberon_id)
--   basis = 'fma_laterality'    via = classe FMA senza lato di cui la struttura è sottoclasse
--   basis = 'uberon_laterality' via = termine UBERON con lato (structure.uberon_id)
--   basis = 'fma_is_a'          via = antenato FMA (rdfs:subClassOf) descritto dalle fonti
--                               cliniche, quando la struttura non ha contenuto proprio
--                               (vedi pipeline/lib/taxonomy.py)
CREATE TABLE IF NOT EXISTS structure_uberon (
  fma_id    TEXT NOT NULL REFERENCES structure(fma_id),
  uberon_id TEXT NOT NULL,
  basis     TEXT NOT NULL
            CHECK (basis IN ('xref', 'fma_laterality', 'uberon_laterality', 'fma_is_a')),
  via_id    TEXT,
  via_label TEXT,
  unsided_label TEXT,           -- nome del concetto più generico (senza lato o antenato)
  PRIMARY KEY (fma_id, uberon_id),
  CHECK ((basis = 'xref') = (via_id IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_structure_uberon_uberon ON structure_uberon(uberon_id);

CREATE TABLE IF NOT EXISTS phenotype (
  hpo_id     TEXT PRIMARY KEY,
  label      TEXT NOT NULL,
  definition TEXT
);

CREATE TABLE IF NOT EXISTS disease (
  mondo_id   TEXT PRIMARY KEY,
  label      TEXT NOT NULL,
  icd11_code TEXT,
  definition TEXT
);

CREATE TABLE IF NOT EXISTS phenotype_structure (
  hpo_id    TEXT NOT NULL REFERENCES phenotype(hpo_id),
  uberon_id TEXT NOT NULL,
  PRIMARY KEY (hpo_id, uberon_id)
);

CREATE INDEX IF NOT EXISTS idx_phenotype_structure_uberon ON phenotype_structure(uberon_id);

CREATE TABLE IF NOT EXISTS disease_phenotype (
  mondo_id  TEXT NOT NULL REFERENCES disease(mondo_id),
  hpo_id    TEXT NOT NULL REFERENCES phenotype(hpo_id),
  frequency TEXT,
  PRIMARY KEY (mondo_id, hpo_id)
);

-- source/source_id: chi asserisce la sede (I2). 'mondo' = assioma sul termine MONDO;
-- 'doid' = assioma RO:0004026 sul termine Disease Ontology source_id.
CREATE TABLE IF NOT EXISTS disease_structure (
  mondo_id  TEXT NOT NULL REFERENCES disease(mondo_id),
  uberon_id TEXT NOT NULL,
  source    TEXT,
  source_id TEXT,
  PRIMARY KEY (mondo_id, uberon_id)
);

CREATE INDEX IF NOT EXISTS idx_disease_structure_uberon ON disease_structure(uberon_id);
CREATE INDEX IF NOT EXISTS idx_disease_phenotype_hpo ON disease_phenotype(hpo_id);

CREATE TABLE IF NOT EXISTS document (
  doc_id     TEXT PRIMARY KEY,
  source     TEXT NOT NULL,
  title      TEXT NOT NULL,
  url        TEXT NOT NULL,
  license    TEXT NOT NULL CHECK (trim(license) <> ''),
  retrieved  TEXT NOT NULL,
  text       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_structure (
  doc_id    TEXT NOT NULL REFERENCES document(doc_id),
  fma_id    TEXT NOT NULL REFERENCES structure(fma_id),
  relevance REAL NOT NULL DEFAULT 1.0,
  PRIMARY KEY (doc_id, fma_id)
);

CREATE TABLE IF NOT EXISTS document_disease (
  doc_id   TEXT NOT NULL REFERENCES document(doc_id),
  mondo_id TEXT NOT NULL REFERENCES disease(mondo_id),
  PRIMARY KEY (doc_id, mondo_id)
);

CREATE TABLE IF NOT EXISTS chunk (
  chunk_id  TEXT PRIMARY KEY,
  doc_id    TEXT NOT NULL REFERENCES document(doc_id),
  ordinal   INTEGER NOT NULL,
  text      TEXT NOT NULL
);

-- Estensione allo schema di SPEC §6: versione e licenza di ogni fonte strutturata
-- caricata. Serve a citare (I2) e ad attribuire (§7) senza che l'API conosca i file grezzi.
CREATE TABLE IF NOT EXISTS source_release (
  source   TEXT PRIMARY KEY,                -- 'mondo' | 'uberon' | 'icd11' | 'bodyparts3d'
  title    TEXT NOT NULL,
  version  TEXT NOT NULL,
  url      TEXT NOT NULL,
  license  TEXT NOT NULL CHECK (trim(license) <> ''),
  attribution TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unmapped (
  kind    TEXT NOT NULL,
  ref_id  TEXT NOT NULL,
  label   TEXT,
  note    TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Colonne aggiunte dopo la prima versione dello schema: un database già esistente le
# riceve con ALTER TABLE (CREATE TABLE IF NOT EXISTS non tocca le tabelle presenti).
_ADDED_COLUMNS = {
    "structure_uberon": [("unsided_label", "TEXT")],
    "disease_structure": [("source", "TEXT"), ("source_id", "TEXT")],
}


# Tabelle il cui vincolo CHECK è cambiato: SQLite non sa modificarlo, quindi su un
# database vecchio si ricreano. Sono tabelle che lo script proprietario riscrive per intero.
_RECREATE_IF_MISSING = {"structure_uberon": "'fma_is_a'"}


def migrate(conn: sqlite3.Connection) -> None:
    for table, marker in _RECREATE_IF_MISSING.items():
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        if row is not None and marker not in row[0]:
            conn.execute(f"DROP TABLE {table}")
    conn.executescript(SCHEMA)
    for table, columns in _ADDED_COLUMNS.items():
        present = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, sqltype in columns:
            if name not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}")


Rows = Iterable[tuple[object, ...]]


def upsert_structures(conn: sqlite3.Connection, rows: Iterable[dict[str, object]]) -> None:
    """Scrive le strutture senza toccare `uberon_id`, che appartiene allo script 04."""
    conn.executemany(
        """
        INSERT INTO structure (fma_id, label_en, label_la, label_it, parent_fma_id,
                               system, region, depth, mesh_file, mesh_node, cx, cy, cz, radius)
        VALUES (:fma_id, :label_en, :label_la, :label_it, :parent_fma_id,
                :system, :region, :depth, :mesh_file, :mesh_node, :cx, :cy, :cz, :radius)
        ON CONFLICT(fma_id) DO UPDATE SET
          label_en=excluded.label_en, label_la=excluded.label_la, label_it=excluded.label_it,
          parent_fma_id=excluded.parent_fma_id,
          system=excluded.system, region=excluded.region, depth=excluded.depth,
          mesh_file=excluded.mesh_file, mesh_node=excluded.mesh_node,
          cx=excluded.cx, cy=excluded.cy, cz=excluded.cz, radius=excluded.radius
        """,
        rows,
    )


def set_uberon_ids(conn: sqlite3.Connection, pairs: Iterable[tuple[str | None, str]]) -> None:
    """pairs = (uberon_id | None, fma_id)."""
    conn.executemany("UPDATE structure SET uberon_id = ? WHERE fma_id = ?", pairs)


def replace_structure_uberon(conn: sqlite3.Connection, rows: Rows) -> None:
    """rows = (fma_id, uberon_id, basis, via_id, via_label, unsided_label)."""
    conn.execute("DELETE FROM structure_uberon")
    conn.executemany(
        """
        INSERT INTO structure_uberon (fma_id, uberon_id, basis, via_id, via_label, unsided_label)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def clinical_uberon_ids(conn: sqlite3.Connection) -> set[str]:
    """Termini UBERON che hanno almeno una malattia o un fenotipo collegato."""
    rows = conn.execute(
        "SELECT uberon_id FROM disease_structure UNION SELECT uberon_id FROM phenotype_structure"
    ).fetchall()
    return {r[0] for r in rows}


def region_clinical_coverage(conn: sqlite3.Connection, region: str) -> tuple[int, int, int]:
    """Strutture con contenuto clinico: (per legame esatto, + ereditato dal lato,
    + ereditato dalla classe più generale)."""
    row = conn.execute(
        """
        WITH clin AS (
          SELECT uberon_id FROM disease_structure UNION SELECT uberon_id FROM phenotype_structure
        )
        SELECT
          COUNT(DISTINCT CASE WHEN su.basis = 'xref' THEN s.fma_id END),
          COUNT(DISTINCT CASE WHEN su.basis <> 'fma_is_a' THEN s.fma_id END),
          COUNT(DISTINCT su.fma_id)
        FROM structure s
        JOIN structure_uberon su ON su.fma_id = s.fma_id
        JOIN clin ON clin.uberon_id = su.uberon_id
        WHERE s.region = ?
        """,
        (region,),
    ).fetchone()
    return int(row[0]), int(row[1]), int(row[2])


def structure_ids(conn: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    """(fma_id, label_en, region) di tutte le strutture."""
    return conn.execute("SELECT fma_id, label_en, region FROM structure ORDER BY fma_id").fetchall()


def upsert_phenotypes(conn: sqlite3.Connection, rows: Rows) -> None:
    conn.executemany(
        """
        INSERT INTO phenotype (hpo_id, label, definition) VALUES (?, ?, ?)
        ON CONFLICT(hpo_id) DO UPDATE SET label=excluded.label, definition=excluded.definition
        """,
        rows,
    )


def upsert_diseases(conn: sqlite3.Connection, rows: Rows) -> None:
    conn.executemany(
        """
        INSERT INTO disease (mondo_id, label, icd11_code, definition) VALUES (?, ?, ?, ?)
        ON CONFLICT(mondo_id) DO UPDATE SET
          label=excluded.label, icd11_code=excluded.icd11_code, definition=excluded.definition
        """,
        rows,
    )


def replace_phenotype_structure(conn: sqlite3.Connection, rows: Rows) -> None:
    conn.execute("DELETE FROM phenotype_structure")
    conn.executemany(
        "INSERT OR IGNORE INTO phenotype_structure (hpo_id, uberon_id) VALUES (?, ?)", rows
    )


def replace_disease_structure(conn: sqlite3.Connection, rows: Rows) -> None:
    """rows = (mondo_id, uberon_id, source, source_id); a parità di coppia vince la prima."""
    conn.execute("DELETE FROM disease_structure")
    conn.executemany(
        """
        INSERT OR IGNORE INTO disease_structure (mondo_id, uberon_id, source, source_id)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def replace_disease_phenotype(conn: sqlite3.Connection, rows: Rows) -> None:
    """Più annotazioni per la stessa coppia: resta la prima frequenza non nulla."""
    conn.execute("DELETE FROM disease_phenotype")
    conn.executemany(
        """
        INSERT INTO disease_phenotype (mondo_id, hpo_id, frequency) VALUES (?, ?, ?)
        ON CONFLICT(mondo_id, hpo_id) DO UPDATE SET
          frequency = COALESCE(disease_phenotype.frequency, excluded.frequency)
        """,
        rows,
    )


def replace_unmapped(conn: sqlite3.Connection, kinds: list[str], rows: Rows) -> None:
    """Sostituisce le righe `unmapped` dei tipi posseduti da uno script."""
    conn.executemany("DELETE FROM unmapped WHERE kind = ?", [(k,) for k in kinds])
    conn.executemany("INSERT INTO unmapped (kind, ref_id, label, note) VALUES (?, ?, ?, ?)", rows)


def unmapped_counts(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    return conn.execute(
        "SELECT kind, COUNT(*) FROM unmapped GROUP BY kind ORDER BY kind"
    ).fetchall()


def region_coverage(conn: sqlite3.Connection, region: str) -> tuple[int, int, int]:
    """(strutture della regione, con uberon_id, con nodo mesh)."""
    row = conn.execute(
        """
        SELECT COUNT(*), COUNT(uberon_id), COUNT(mesh_node) FROM structure WHERE region = ?
        """,
        (region,),
    ).fetchone()
    return int(row[0]), int(row[1]), int(row[2])


def region_unmapped(conn: sqlite3.Connection, region: str) -> list[tuple[str, str, int]]:
    """Strutture della regione senza uberon_id: (fma_id, label, depth)."""
    return conn.execute(
        """
        SELECT fma_id, label_en, depth FROM structure
        WHERE region = ? AND uberon_id IS NULL ORDER BY depth, label_en
        """,
        (region,),
    ).fetchall()


def upsert_source_release(
    conn: sqlite3.Connection,
    source: str,
    title: str,
    version: str,
    url: str,
    license: str,
    attribution: str,
) -> None:
    conn.execute(
        """
        INSERT INTO source_release (source, title, version, url, license, attribution)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source) DO UPDATE SET
          title=excluded.title, version=excluded.version, url=excluded.url,
          license=excluded.license, attribution=excluded.attribution
        """,
        (source, title, version, url, license, attribution),
    )
