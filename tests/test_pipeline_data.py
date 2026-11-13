"""Test sui dati di atlas.db: criteri di accettazione della Fase 1 e invarianti.

Girano sull'artefatto reale; vengono saltati se la pipeline non è stata eseguita.
"""

import re
import sqlite3
from collections.abc import Iterator

import pytest

from pipeline.lib import config

pytestmark = pytest.mark.skipif(not config.DB_PATH.exists(), reason="atlas.db non generato")

REGION = "abdomen"  # regione di riferimento per i criteri di accettazione di Fase 1


@pytest.fixture(scope="module")
def conn() -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(f"{config.DB_PATH.as_uri()}?mode=ro", uri=True)
    yield c
    c.close()


def scalar(conn: sqlite3.Connection, sql: str, *args: object) -> int:
    return int(conn.execute(sql, args).fetchone()[0])


# ─── Accettazione Fase 1 ────────────────────────────────────────────────────
def test_at_least_80_abdominal_structures(conn: sqlite3.Connection) -> None:
    assert scalar(conn, "SELECT COUNT(*) FROM structure WHERE region = ?", REGION) >= 80


def test_liver_descends_at_least_5_levels(conn: sqlite3.Connection) -> None:
    levels = scalar(
        conn,
        """
        WITH RECURSIVE descend(fma_id, depth) AS (
          SELECT fma_id, 0 FROM structure WHERE fma_id = 'FMA:7197'
          UNION ALL
          SELECT s.fma_id, d.depth + 1
          FROM structure s JOIN descend d ON s.parent_fma_id = d.fma_id
          WHERE d.depth < 8
        )
        SELECT COUNT(DISTINCT depth) FROM descend
        """,
    )
    assert levels >= 5


@pytest.mark.parametrize("region", config.REGION_KEYS)
def test_unmapped_report_exists_and_matches_db(conn: sqlite3.Connection, region: str) -> None:
    report = config.REPORTS / f"unmapped_{region}.md"
    assert report.exists(), "eseguire 04_bridge_fma_uberon"
    total = scalar(conn, "SELECT COUNT(*) FROM structure WHERE region = ?", region)
    mapped = scalar(conn, "SELECT COUNT(uberon_id) FROM structure WHERE region = ?", region)
    text = report.read_text("utf-8")
    assert f"**{total}**" in text and f"**{mapped}**" in text
    assert (config.REPORTS / "coverage.md").exists()


def test_no_unmapped_structure_is_silent(conn: sqlite3.Connection) -> None:
    """Ogni struttura senza uberon_id è registrata in `unmapped`, non nascosta."""
    silent = scalar(
        conn,
        """
        SELECT COUNT(*) FROM structure s WHERE s.uberon_id IS NULL AND NOT EXISTS (
          SELECT 1 FROM unmapped u WHERE u.ref_id = s.fma_id
            AND u.kind IN ('fma_no_uberon', 'fma_multi_uberon'))
        """,
    )
    assert silent == 0


# ─── Fase 7: ogni regione è una riesecuzione con un filtro diverso ──────────
@pytest.mark.parametrize("region", config.REGION_KEYS)
def test_every_region_has_a_glb_with_nodes(conn: sqlite3.Connection, region: str) -> None:
    nodes = scalar(conn, "SELECT COUNT(*) FROM structure WHERE mesh_file = ?", f"{region}.glb")
    assert nodes > 0
    assert (config.MESHES / f"{region}.glb").exists()


def test_each_node_lives_in_exactly_one_glb(conn: sqlite3.Connection) -> None:
    """Un FMA ID non compare in due file: la scena lo può mappare senza ambiguità (I1)."""
    import json

    geometry = json.loads(config.GEOMETRY_JSON.read_text("utf-8"))
    seen: dict[str, str] = {}
    for key, region in geometry["regions"].items():
        for fma_id in region["nodes"]:
            assert fma_id not in seen, f"{fma_id} in {seen.get(fma_id)} e {key}"
            seen[fma_id] = key
    in_db = scalar(conn, "SELECT COUNT(*) FROM structure WHERE mesh_node IS NOT NULL")
    assert in_db == len(seen)


def test_every_mesh_structure_has_centroid_and_radius(conn: sqlite3.Connection) -> None:
    bad = scalar(
        conn,
        """
        SELECT COUNT(*) FROM structure WHERE mesh_file IS NOT NULL
          AND (cx IS NULL OR cy IS NULL OR cz IS NULL OR radius IS NULL OR radius <= 0)
        """,
    )
    assert bad == 0


# ─── Invarianti ─────────────────────────────────────────────────────────────
ID_FORMATS = [
    ("structure", "fma_id", r"FMA:\d+"),
    ("structure", "uberon_id", r"UBERON:\d{7}"),
    ("phenotype", "hpo_id", r"HP:\d{7}"),
    ("disease", "mondo_id", r"MONDO:\d{7}"),
    ("phenotype_structure", "uberon_id", r"UBERON:\d{7}"),
    ("disease_structure", "uberon_id", r"UBERON:\d{7}"),
]


@pytest.mark.parametrize(("table", "column", "pattern"), ID_FORMATS)
def test_identifier_format(conn: sqlite3.Connection, table: str, column: str, pattern: str) -> None:
    rx = re.compile(pattern)
    rows = conn.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL")
    bad = [r[0] for r in rows if not rx.fullmatch(r[0])]
    assert not bad, bad[:5]


def test_mesh_node_is_the_fma_id(conn: sqlite3.Connection) -> None:
    """I1: il nome del nodo nel GLB è l'FMA ID."""
    assert scalar(conn, "SELECT COUNT(*) FROM structure WHERE mesh_node <> fma_id") == 0


def test_referential_integrity(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_every_source_has_a_license(conn: sqlite3.Connection) -> None:
    sources = {r[0] for r in conn.execute("SELECT source FROM source_release")}
    assert {"bodyparts3d", "fma", "uberon", "hpo", "hpoa", "mondo", "doid", "icd11"} <= sources
    assert scalar(conn, "SELECT COUNT(*) FROM source_release WHERE trim(license) = ''") == 0
    assert scalar(conn, "SELECT COUNT(*) FROM document WHERE trim(license) = ''") == 0


def test_exact_links_mirror_structure_uberon_id(conn: sqlite3.Connection) -> None:
    """`structure.uberon_id` resta il solo xref esatto; `structure_uberon` lo contiene."""
    exact = conn.execute("SELECT fma_id, uberon_id FROM structure_uberon WHERE basis = 'xref'")
    on_structure = conn.execute(
        "SELECT fma_id, uberon_id FROM structure WHERE uberon_id IS NOT NULL"
    )
    assert set(exact.fetchall()) == set(on_structure.fetchall())


def test_inherited_links_are_sided_variants(conn: sqlite3.Connection) -> None:
    """Ogni legame ereditato collega "Right/Left X" a "X" (I5: niente analogie libere)."""
    from pipeline.lib.laterality import unsided_name

    rows = conn.execute(
        """
        SELECT s.label_en, su.basis, su.via_label FROM structure_uberon su
        JOIN structure s USING (fma_id) WHERE su.basis <> 'xref'
        """
    ).fetchall()
    assert rows, "l'ereditarietà destra/sinistra non ha prodotto legami"
    for label, basis, via_label in rows:
        if basis == "fma_laterality":
            assert unsided_name(label) == via_label.strip().lower(), (label, via_label)
        else:  # uberon_laterality: via_label è il termine UBERON con lato
            assert unsided_name(via_label) is not None, (label, via_label)


def test_uberon_route_does_not_widen_the_structure(conn: sqlite3.Connection) -> None:
    """Regressione: UBERON usa "left eye" come xref di "Left eyeball"; risalendo is_a si
    arriverebbe a "eye" (occhio intero, annessi compresi), che non è il bulbo."""
    eye_on_eyeball = scalar(
        conn,
        """
        SELECT COUNT(*) FROM structure_uberon su JOIN structure s USING (fma_id)
        WHERE s.label_en IN ('Left eyeball', 'Right eyeball') AND su.uberon_id = 'UBERON:0000970'
        """,
    )
    assert eye_on_eyeball == 0
    missing_name = scalar(
        conn,
        "SELECT COUNT(*) FROM structure_uberon WHERE basis <> 'xref' AND unsided_label IS NULL",
    )
    assert missing_name == 0


def test_every_disease_site_has_a_source(conn: sqlite3.Connection) -> None:
    """I2: per ogni legame malattia → sede si sa chi lo asserisce (MONDO o Disease Ontology)."""
    assert scalar(conn, "SELECT COUNT(*) FROM disease_structure WHERE source IS NULL") == 0
    bad = scalar(
        conn,
        """
        SELECT COUNT(*) FROM disease_structure
        WHERE NOT ((source = 'mondo' AND source_id = mondo_id)
                OR (source = 'doid' AND source_id LIKE 'DOID:%'))
        """,
    )
    assert bad == 0


def test_laterality_reaches_the_limbs(conn: sqlite3.Connection) -> None:
    """La ragione dell'ereditarietà: gli arti avevano quasi solo strutture con lato."""
    # prima dell'ereditarietà: 2 strutture con patologie o segni negli arti superiori
    with_content = scalar(
        conn,
        """
        WITH clin AS (
          SELECT uberon_id FROM disease_structure UNION SELECT uberon_id FROM phenotype_structure
        )
        SELECT COUNT(DISTINCT s.fma_id) FROM structure s
        JOIN structure_uberon su ON su.fma_id = s.fma_id
        JOIN clin ON clin.uberon_id = su.uberon_id
        WHERE s.region = 'upper_limb'
        """,
    )
    assert with_content >= 50


def test_clinical_graph_is_populated(conn: sqlite3.Connection) -> None:
    assert scalar(conn, "SELECT COUNT(*) FROM phenotype") > 10_000
    assert scalar(conn, "SELECT COUNT(*) FROM disease") > 20_000
    assert scalar(conn, "SELECT COUNT(*) FROM disease_phenotype") > 100_000
    assert scalar(conn, "SELECT COUNT(*) FROM phenotype_structure") > 1_000
    assert scalar(conn, "SELECT COUNT(*) FROM disease_structure") > 1_000
    # il ponte funziona: dal fegato si arriva a malattie e fenotipi
    liver = "(SELECT uberon_id FROM structure WHERE fma_id = 'FMA:7197')"
    assert scalar(conn, f"SELECT COUNT(*) FROM disease_structure WHERE uberon_id = {liver}") > 0
    assert scalar(conn, f"SELECT COUNT(*) FROM phenotype_structure WHERE uberon_id = {liver}") > 0
