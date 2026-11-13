"""Percorsi e costanti condivise dalla pipeline."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
MESHES = DATA / "meshes"
DB_PATH = DATA / "atlas.db"

BP3D_DIR = RAW / "bodyparts3d"
BP3D_ZIP = BP3D_DIR / "partof_BP3D_4.0_obj_99.zip"
BP3D_PARTS = BP3D_DIR / "partof_parts_list_e.txt"
BP3D_ELEMENTS = BP3D_DIR / "partof_element_parts.txt"

MONDO_OBO = RAW / "ontologies" / "mondo.obo"
UBERON_OBO = RAW / "ontologies" / "uberon-basic.obo"

ICD11_DIR = RAW / "icd11"
ICD11_TABULATION = ICD11_DIR / "SimpleTabulation-ICD-11-MMS-en.txt"
ICD11_RELEASE_FILE = ICD11_DIR / "RELEASE"

ACTIVE_REGION = "abdomen"
