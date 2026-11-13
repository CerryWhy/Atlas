"""Schema di atlas.db (SPEC §6) e helper di connessione per la pipeline.

Tutto l'SQL di scrittura della pipeline vive qui (SPEC §11).
La tabella virtuale sqlite-vec per gli embedding arriva in Fase 3.
"""

import sqlite3
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

CREATE TABLE IF NOT EXISTS disease_phenotype (
  mondo_id  TEXT NOT NULL REFERENCES disease(mondo_id),
  hpo_id    TEXT NOT NULL REFERENCES phenotype(hpo_id),
  frequency TEXT,
  PRIMARY KEY (mondo_id, hpo_id)
);

CREATE TABLE IF NOT EXISTS disease_structure (
  mondo_id  TEXT NOT NULL REFERENCES disease(mondo_id),
  uberon_id TEXT NOT NULL,
  PRIMARY KEY (mondo_id, uberon_id)
);

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


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def upsert_structure(conn: sqlite3.Connection, row: dict[str, object]) -> None:
    conn.execute(
        """
        INSERT INTO structure (fma_id, label_en, label_la, label_it, uberon_id, parent_fma_id,
                               system, region, depth, mesh_file, mesh_node, cx, cy, cz, radius)
        VALUES (:fma_id, :label_en, :label_la, :label_it, :uberon_id, :parent_fma_id,
                :system, :region, :depth, :mesh_file, :mesh_node, :cx, :cy, :cz, :radius)
        ON CONFLICT(fma_id) DO UPDATE SET
          label_en=excluded.label_en, label_la=excluded.label_la, label_it=excluded.label_it,
          uberon_id=excluded.uberon_id, parent_fma_id=excluded.parent_fma_id,
          system=excluded.system, region=excluded.region, depth=excluded.depth,
          mesh_file=excluded.mesh_file, mesh_node=excluded.mesh_node,
          cx=excluded.cx, cy=excluded.cy, cz=excluded.cz, radius=excluded.radius
        """,
        row,
    )


def upsert_disease(
    conn: sqlite3.Connection,
    mondo_id: str,
    label: str,
    icd11_code: str | None,
    definition: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO disease (mondo_id, label, icd11_code, definition)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(mondo_id) DO UPDATE SET
          label=excluded.label, icd11_code=excluded.icd11_code, definition=excluded.definition
        """,
        (mondo_id, label, icd11_code, definition),
    )


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


def link_disease_structure(conn: sqlite3.Connection, mondo_id: str, uberon_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO disease_structure (mondo_id, uberon_id) VALUES (?, ?)",
        (mondo_id, uberon_id),
    )
