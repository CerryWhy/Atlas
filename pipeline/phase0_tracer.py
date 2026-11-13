"""Fase 0 — proiettile tracciante.

Produce `data/atlas.db` con UNA struttura (fegato, FMA:7197) e TRE malattie reali
da MONDO, più `data/meshes/liver.glb`. Tutti gli ID vengono letti da file
scaricati (I5): lo script fallisce se uno solo non si trova.

Prerequisiti in data/raw/ (vedi README):
  bodyparts3d/partof_BP3D_4.0_obj_99.zip, partof_element_parts.txt, partof_parts_list_e.txt
  ontologies/mondo.obo, ontologies/uberon-basic.obo
  icd11/SimpleTabulation-ICD-11-MMS-en.txt

Idempotente: riscrive le stesse righe con UPSERT; il GLB viene rigenerato solo
se manca.

Uso:  python -m pipeline.phase0_tracer
"""

import csv
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from pipeline.lib import config, db, mesh, obo

LIVER_FMA = "FMA:7197"
LIVER_GLB = "liver.glb"

# Scelte a mano tra i termini MONDO che hanno un assioma
# disease_has_location UBERON:0002107 e un xref ICD-11 foundation.
# Lo script verifica entrambe le condizioni sul file: non sono assunte.
PHASE0_DISEASES = ["MONDO:0002691", "MONDO:0002387", "MONDO:0700051"]
LOCATION_RELATIONS = {"disease_has_location", "disease_has_inflammation_site"}


def bp3d_id(fma_id: str) -> str:
    return fma_id.replace(":", "")


def read_bp3d_label(fma_id: str) -> str:
    with config.BP3D_PARTS.open(encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if row and row[0] == bp3d_id(fma_id):
                return row[2].strip()
    raise LookupError(f"{fma_id} assente in {config.BP3D_PARTS.name}")


def read_bp3d_elements(fma_id: str) -> list[str]:
    elements: list[str] = []
    with config.BP3D_ELEMENTS.open(encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if row and row[0] == bp3d_id(fma_id):
                elements.append(row[2].strip())
    if not elements:
        raise LookupError(f"{fma_id} senza elementi in {config.BP3D_ELEMENTS.name}")
    return sorted(set(elements))


def uberon_for_fma(fma_id: str) -> str:
    hits = [
        t.id
        for t in obo.iter_terms(config.UBERON_OBO)
        if not t.obsolete and t.id.startswith("UBERON:") and fma_id in t.xrefs
    ]
    if len(hits) != 1:
        raise LookupError(f"Crosswalk UBERON per {fma_id} non univoco: {hits}")
    return hits[0]


def icd11_foundation_to_code() -> dict[str, str]:
    """Foundation entity id → codice MMS, dalla Simple Tabulation WHO."""
    out: dict[str, str] = {}
    with config.ICD11_TABULATION.open(encoding="utf-8-sig") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if len(row) < 3 or not row[0].startswith("http://id.who.int/icd/entity/"):
                continue
            code = row[2].strip()
            if code:
                out[row[0].rsplit("/", 1)[1]] = code
    return out


def build_mesh(fma_id: str, out: Path) -> mesh.Geometry:
    m = mesh.load_elements(config.BP3D_ZIP, read_bp3d_elements(fma_id))
    geom = mesh.geometry_of(m)
    if out.exists():
        return geom
    cli = find_gltf_transform()
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.glb"
        mesh.export_glb({fma_id: m}, raw)
        mesh.draco_compress(raw, out, cli)
    return geom


def find_gltf_transform() -> list[str]:
    bin_dir = config.ROOT / "node_modules" / ".bin"
    for name in ("gltf-transform.cmd", "gltf-transform"):
        exe = bin_dir / name
        if exe.exists():
            return [str(exe)]
    found = shutil.which("gltf-transform")
    if found:
        return [found]
    raise FileNotFoundError("gltf-transform non trovato: eseguire `npm install` nella root")


CC_LICENSES = {
    "http://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "http://creativecommons.org/licenses/by/3.0/": "CC BY 3.0",
}


def register_sources(conn: sqlite3.Connection) -> None:
    """Versione e licenza di ogni fonte, lette dai file quando il file le dichiara."""
    mondo_lic = CC_LICENSES[obo.license_url(config.MONDO_OBO)]
    uberon_lic = CC_LICENSES[obo.license_url(config.UBERON_OBO)]
    icd_release = config.ICD11_RELEASE_FILE.read_text(encoding="utf-8").strip()
    db.upsert_source_release(
        conn,
        "bodyparts3d",
        "BodyParts3D",
        "4.0 (LATEST)",
        "https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html",
        # Licenza dichiarata alla pagina lic.html del Licensor (non nel file).
        "CC BY 4.0",
        "BodyParts3D, © The Database Center for Life Science, "
        "licensed under CC Attribution 4.0 International.",
    )
    db.upsert_source_release(
        conn,
        "mondo",
        "Mondo Disease Ontology",
        obo.data_version(config.MONDO_OBO),
        "https://mondo.monarchinitiative.org/",
        mondo_lic,
        f"Mondo Disease Ontology, Monarch Initiative, licensed under {mondo_lic}.",
    )
    db.upsert_source_release(
        conn,
        "uberon",
        "Uberon multi-species anatomy ontology",
        obo.data_version(config.UBERON_OBO),
        "https://obophenotype.github.io/uberon/",
        uberon_lic,
        f"Uberon anatomy ontology, licensed under {uberon_lic}.",
    )
    db.upsert_source_release(
        conn,
        "icd11",
        "ICD-11 for Mortality and Morbidity Statistics",
        icd_release,
        f"https://icd.who.int/browse/{icd_release}/mms/en",
        # Licenza dal documento WHO icd11-license.pdf (CC BY-ND 3.0 IGO).
        "CC BY-ND 3.0 IGO",
        f"ICD-11 MMS {icd_release}, World Health Organization, licensed under "
        "CC BY-ND 3.0 IGO. Codes reproduced without modification.",
    )


def main() -> int:
    label_en = read_bp3d_label(LIVER_FMA)
    uberon_id = uberon_for_fma(LIVER_FMA)
    geom = build_mesh(LIVER_FMA, config.MESHES / LIVER_GLB)

    terms = obo.load_terms(config.MONDO_OBO, set(PHASE0_DISEASES))
    foundation = icd11_foundation_to_code()

    conn = db.connect(config.DB_PATH)
    with conn:
        db.migrate(conn)
        register_sources(conn)
        db.upsert_structure(
            conn,
            {
                "fma_id": LIVER_FMA,
                "label_en": label_en,
                "label_la": None,  # Fase 1: da FMA/TA, non inventato qui
                "label_it": None,
                "uberon_id": uberon_id,
                "parent_fma_id": None,
                "system": "digestive",
                "region": config.ACTIVE_REGION,
                "depth": 0,
                "mesh_file": LIVER_GLB,
                "mesh_node": LIVER_FMA,
                "cx": geom.cx,
                "cy": geom.cy,
                "cz": geom.cz,
                "radius": geom.radius,
            },
        )
        for mondo_id in PHASE0_DISEASES:
            term = terms.get(mondo_id)
            if term is None or term.obsolete:
                raise LookupError(f"{mondo_id} assente o obsoleto in mondo.obo")
            if (
                rel := next(
                    (
                        r
                        for r, tgt in term.relations
                        if tgt == uberon_id and r in LOCATION_RELATIONS
                    ),
                    None,
                )
            ) is None:
                raise LookupError(f"{mondo_id} non ha assioma di sede su {uberon_id}")
            codes = {
                foundation[x.split(":", 1)[1]]
                for x in term.xrefs
                if x.startswith("icd11.foundation:") and x.split(":", 1)[1] in foundation
            }
            if len(codes) != 1:
                raise LookupError(f"{mondo_id}: codice ICD-11 MMS non univoco: {codes}")
            code = codes.pop()
            db.upsert_disease(conn, mondo_id, term.name, code, term.definition)
            db.link_disease_structure(conn, mondo_id, uberon_id)
            print(f"  {mondo_id}  {code:<8} {term.name}  ({rel})")
    conn.close()
    print(f"OK: {LIVER_FMA} ({label_en}) <-> {uberon_id}, r={geom.radius:.3f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
