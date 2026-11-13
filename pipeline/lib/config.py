"""Percorsi e costanti condivise dalla pipeline."""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
BUILD = DATA / "build"  # intermedi tra script (es. geometria calcolata da 02)
REPORTS = DATA / "reports"
MESHES = DATA / "meshes"
DB_PATH = DATA / "atlas.db"
MANIFEST = RAW / "MANIFEST.json"

BP3D_DIR = RAW / "bodyparts3d"
BP3D_ZIP = BP3D_DIR / "partof_BP3D_4.0_obj_99.zip"
BP3D_PARTS = BP3D_DIR / "partof_parts_list_e.txt"
BP3D_ELEMENTS = BP3D_DIR / "partof_element_parts.txt"
BP3D_TREE = BP3D_DIR / "partof_inclusion_relation_list.txt"

ONTO = RAW / "ontologies"
FMA_OWL = ONTO / "fma.owl"
MONDO_OBO = ONTO / "mondo.obo"
UBERON_OBO = ONTO / "uberon-basic.obo"
HPO_OBO = ONTO / "hp-full.obo"  # la variante "full" contiene le definizioni logiche
HPOA = ONTO / "phenotype.hpoa"
DOID_OWL = ONTO / "doid.owl"  # gli assiomi di sede (RO:0004026) sono solo nell'OWL

ICD11_RELEASE = "2026-01"
ICD11_DIR = RAW / "icd11"
ICD11_ZIP = ICD11_DIR / "SimpleTabulation-ICD-11-MMS-en.zip"
ICD11_TABULATION = ICD11_DIR / "SimpleTabulation-ICD-11-MMS-en.txt"
ICD11_RELEASE_FILE = ICD11_DIR / "RELEASE"

GEOMETRY_JSON = BUILD / "geometry.json"

# ─── Regione attiva ─────────────────────────────────────────────────────────
# Il confine della regione è geometrico e riproducibile (vedi 02_build_meshes):
#   - box del concetto BodyParts3D indicato (per FMA "abdomen" include la pelvi);
#   - tetto opzionale: una mesh sotto la quale l'elemento deve trovarsi (il diaframma).
ACTIVE_REGION = "abdomen"
REGION_BOUNDARY_FMA = {"abdomen": "FMA:9577"}  # abdomen
REGION_CEILING_FMA = {"abdomen": "FMA:13295"}  # diaphragm
# Un elemento è nella regione se almeno questa quota dei suoi vertici cade nel box…
ELEMENT_MIN_FRACTION = 0.5
# …e un concetto è "della regione" se almeno questa quota dei suoi elementi vi cade.
REGION_MIN_FRACTION = 0.5


@dataclass(frozen=True)
class Source:
    dest: Path
    url: str


_BP3D = "https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST"
SOURCES: list[Source] = [
    Source(BP3D_DIR / "README_e.html", f"{_BP3D}/README_e.html"),
    Source(BP3D_PARTS, f"{_BP3D}/partof_parts_list_e.txt"),
    Source(BP3D_ELEMENTS, f"{_BP3D}/partof_element_parts.txt"),
    Source(BP3D_TREE, f"{_BP3D}/partof_inclusion_relation_list.txt"),
    Source(BP3D_ZIP, f"{_BP3D}/partof_BP3D_4.0_obj_99.zip"),
    Source(FMA_OWL, "http://sig.biostr.washington.edu/share/downloads/fma/release/latest/fma.owl"),
    Source(
        ONTO / "fma.LICENSE",
        "http://sig.biostr.washington.edu/share/downloads/fma/release/latest/LICENSE",
    ),
    Source(MONDO_OBO, "http://purl.obolibrary.org/obo/mondo.obo"),
    Source(UBERON_OBO, "http://purl.obolibrary.org/obo/uberon/basic.obo"),
    Source(HPO_OBO, "http://purl.obolibrary.org/obo/hp/hp-full.obo"),
    Source(HPOA, "http://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa"),
    Source(DOID_OWL, "http://purl.obolibrary.org/obo/doid.owl"),
    Source(
        ICD11_ZIP,
        f"https://icdcdn.who.int/static/releasefiles/{ICD11_RELEASE}/"
        "SimpleTabulation-ICD-11-MMS-en.zip",
    ),
]
