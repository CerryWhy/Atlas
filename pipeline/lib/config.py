"""Percorsi e costanti condivise dalla pipeline."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

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

# Nomi italiani: voci Wikidata con un FMA ID (P1402) e la loro etichetta italiana.
# Dati Wikidata: CC0 1.0. Vedi pipeline/lib/wikidata.py per le regole di accettazione.
WIKIDATA_DIR = RAW / "wikidata"
WIKIDATA_LABELS_IT = WIKIDATA_DIR / "fma_labels_it.json"
WIKIDATA_QUERY = """
SELECT ?item ?fma ?label WHERE {
  ?item wdt:P1402 ?fma .
  OPTIONAL { ?item rdfs:label ?label . FILTER(LANG(?label) = "it") }
}
"""


# ─── Regioni ────────────────────────────────────────────────────────────────
# Ogni regione è un GLB. Un elemento mesh finisce in UNA sola regione, decisa da queste
# regole nell'ordine in cui compaiono (la prima che lo reclama vince):
#   - `concepts`: gli elementi del concetto BodyParts3D indicato e di tutte le sue parti;
#   - `box_fma`: elementi la cui maggior parte dei vertici cade nel box di quel concetto
#     (per FMA "abdomen" il box include la pelvi), e che non poggiano sopra `ceiling_fma`
#     (il diaframma: toglie cuore e basi polmonari dall'addome).
# Gli elementi che nessuna regola reclama (vasi, nervi, visceri che attraversano più
# regioni) vanno alla regione dell'elemento reclamato più vicino.
# Aggiungere o cambiare una regione è un cambio di questa tabella, non dell'applicazione.
@dataclass(frozen=True)
class RegionRule:
    key: str
    concepts: tuple[str, ...] = ()
    box_fma: str | None = None
    ceiling_fma: str | None = None


REGIONS: tuple[RegionRule, ...] = (
    RegionRule("head", concepts=("FMA:7154",)),  # head
    RegionRule("neck", concepts=("FMA:7155",)),  # neck
    RegionRule("upper_limb", concepts=("FMA:7185", "FMA:7186")),  # right/left upper limb
    RegionRule("lower_limb", concepts=("FMA:7184", "FMA:7187", "FMA:7188")),  # lower limbs
    RegionRule("abdomen", box_fma="FMA:9577", ceiling_fma="FMA:13295"),  # abdomen; diaphragm
    RegionRule("thorax", concepts=("FMA:9576",)),  # thorax
)
REGION_KEYS: tuple[str, ...] = tuple(r.key for r in REGIONS)

# Un elemento è nel box di una regola `box_fma` se almeno questa quota dei suoi vertici ci cade…
ELEMENT_MIN_FRACTION = 0.5
# …e un concetto è "di una regione" se almeno questa quota dei suoi elementi vi cade.
REGION_MIN_FRACTION = 0.5


@dataclass(frozen=True)
class Source:
    dest: Path
    url: str
    # Copie dello STESSO file da provare se `url` non risponde (es. una rete che non
    # lascia passare HTTP in chiaro). 01 registra nel MANIFEST l'URL usato davvero.
    mirrors: tuple[str, ...] = ()


# Wayback Machine: copia d'archivio della release FMA ufficiale, servita in HTTPS.
# `id_` chiede il file originale, senza la barra di navigazione dell'archivio.
_FMA_RELEASE = "http://sig.biostr.washington.edu/share/downloads/fma/release/latest"
_WAYBACK = "https://web.archive.org/web/2025id_/"


_BP3D = "https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST"
SOURCES: list[Source] = [
    Source(BP3D_DIR / "README_e.html", f"{_BP3D}/README_e.html"),
    Source(BP3D_PARTS, f"{_BP3D}/partof_parts_list_e.txt"),
    Source(BP3D_ELEMENTS, f"{_BP3D}/partof_element_parts.txt"),
    Source(BP3D_TREE, f"{_BP3D}/partof_inclusion_relation_list.txt"),
    Source(BP3D_ZIP, f"{_BP3D}/partof_BP3D_4.0_obj_99.zip"),
    Source(FMA_OWL, f"{_FMA_RELEASE}/fma.owl", (f"{_WAYBACK}{_FMA_RELEASE}/fma.owl",)),
    Source(
        ONTO / "fma.LICENSE",
        f"{_FMA_RELEASE}/LICENSE",
        (f"{_WAYBACK}{_FMA_RELEASE}/LICENSE",),
    ),
    Source(MONDO_OBO, "https://purl.obolibrary.org/obo/mondo.obo"),
    Source(UBERON_OBO, "https://purl.obolibrary.org/obo/uberon/basic.obo"),
    Source(HPO_OBO, "https://purl.obolibrary.org/obo/hp/hp-full.obo"),
    Source(HPOA, "https://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa"),
    Source(DOID_OWL, "https://purl.obolibrary.org/obo/doid.owl"),
    Source(
        ICD11_ZIP,
        f"https://icdcdn.who.int/static/releasefiles/{ICD11_RELEASE}/"
        "SimpleTabulation-ICD-11-MMS-en.zip",
    ),
    Source(
        WIKIDATA_LABELS_IT,
        "https://query.wikidata.org/sparql?"
        + urlencode({"format": "json", "query": " ".join(WIKIDATA_QUERY.split())}),
    ),
]


# ─── Ereditarietà dalla classe più generale (pipeline/lib/taxonomy.py) ─────────
# Quanti passi rdfs:subClassOf si risalgono al massimo, e quante sottoclassi FMA può
# avere l'antenato prima di essere considerato troppo generico per dire qualcosa della
# struttura. Valori iniziali da tarare leggendo data/reports/is_a_links.md.
ISA_MAX_HOPS = 3
ISA_MAX_DESCENDANTS = 300

# ─── Tessuto di una struttura, per i livelli della scena (pelle → muscoli → ossa) ──
# Classi FMA cercate per NOME esatto nel file (nessun ID scritto a mano: I5); una
# struttura prende il tessuto della classe marcata più vicina risalendo rdfs:subClassOf.
# Un nome che non si trova viene segnalato da 04 e semplicemente non marca nulla.
TISSUE_CLASSES: dict[str, str] = {
    "Skin": "skin",
    "Muscle organ": "muscle",
    "Tendon": "muscle",
    "Fascia": "muscle",
    "Bone organ": "bone",
    "Cartilage organ": "bone",
    "Ligament": "bone",
}

# ─── Corpus testuale (Fase 3) ─────────────────────────────────────────────────
# Gli URL di MedlinePlus e StatPearls cambiano a ogni rilascio: 05 li ricava dagli
# indici ufficiali (pagina XML di MedlinePlus, file_list.csv dell'FTP NCBI).
DOCS = RAW / "docs"
MEDLINEPLUS_XML = DOCS / "mplus_topics.xml"
MEDLINEPLUS_INDEX = "https://medlineplus.gov/xml.html"
ORPHANET_XML = DOCS / "orphanet_en_product1.xml"
ORPHANET_URL = "https://www.orphadata.com/data/xml/en_product1.xml"
STATPEARLS_TGZ = DOCS / "statpearls_NBK430685.tar.gz"
STATPEARLS_ACCESSION = "NBK430685"
# Solo l'FTP ufficiale NCBI (SPEC §3): niente recupero sistematico da altre vie.
NCBI_LITARCH = "https://ftp.ncbi.nlm.nih.gov/pub/litarch/"

# ─── Embedding (07) ───────────────────────────────────────────────────────────
# Modello multilingue locale (SPEC §4: nessun testo esce per gli embedding).
# E5 vuole i prefissi "query: " / "passage: ". Cambiare modello rifà tutti i vettori.
EMBED_MODEL = "intfloat/multilingual-e5-base"
CHUNK_CHARS = 1500  # obiettivo per chunk: ~350 token, sotto il limite di 512 di E5
