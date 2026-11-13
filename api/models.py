"""Modelli di risposta. Lo schema OpenAPI generato da qui è la fonte dei tipi TS."""

from pydantic import BaseModel, Field

FMA_PATTERN = r"^FMA:\d+$"
MONDO_PATTERN = r"^MONDO:\d{7}$"
HPO_PATTERN = r"^HP:\d{7}$"


class Citation(BaseModel):
    """Riferimento a un documento apribile (I2)."""

    source: str
    title: str
    url: str
    version: str
    license: str


class Disease(BaseModel):
    mondo_id: str = Field(pattern=MONDO_PATTERN)
    label: str
    icd11_code: str | None
    # True se la malattia arriva solo dalla versione senza lato della struttura
    inherited: bool
    citations: list[Citation] = Field(min_length=1)


class Phenotype(BaseModel):
    hpo_id: str = Field(pattern=HPO_PATTERN)
    label: str
    inherited: bool
    citations: list[Citation] = Field(min_length=1)


class InheritedLink(BaseModel):
    """Legame clinico preso da un concetto più generale della struttura: la sua versione
    senza lato, oppure (se non basta) l'antenato FMA più vicino descritto dalle fonti."""

    uberon_id: str
    basis: str  # 'fma_laterality' | 'uberon_laterality' | 'fma_is_a'
    unsided_label: str
    # False se il termine senza lato non porta né malattie né segni
    carries_content: bool
    citations: list[Citation] = Field(min_length=1)


class StructureRef(BaseModel):
    """Riferimento leggero a una struttura (briciole di pane, parti)."""

    fma_id: str = Field(pattern=FMA_PATTERN)
    label_en: str
    label_it: str | None


class ChildRef(StructureRef):
    has_uberon: bool


class Structure(BaseModel):
    fma_id: str = Field(pattern=FMA_PATTERN)
    label_en: str
    label_la: str | None
    label_it: str | None
    uberon_id: str | None
    parent_fma_id: str | None
    system: str | None
    region: str | None
    depth: int
    mesh_file: str | None
    mesh_node: str | None
    centroid: tuple[float, float, float] | None
    radius: float | None
    citations: list[Citation]
    inherited_from: list[InheritedLink]
    ancestors: list[StructureRef]
    children: list[ChildRef]
    mesh_nodes: list[str]
    diseases: list[Disease]
    phenotypes: list[Phenotype]
    documents: list["Reading"]


class Reading(BaseModel):
    """Un documento del corpus collegato alla struttura (Fase 3).

    `citation` è il documento stesso (apribile, con licenza); `link` spiega perché è
    qui: il capitolo tratta la struttura, o tratta una malattia con sede in essa."""

    doc_id: str
    source: str  # 'statpearls' | 'medlineplus' | 'orphanet'
    title: str
    # 'anatomy_title' | 'mesh_anatomy' | 'disease_site' | 'disease_site_part' | 'container'
    basis: str
    relevance: float
    link: str  # es. "Tratta questa struttura" | "Dalla struttura che la contiene: Liver (FMA:7197)"
    citation: Citation


class SearchHit(BaseModel):
    """Un chunk restituito dalla ricerca vettoriale, con il documento da citare."""

    chunk_id: str
    doc_id: str
    text: str
    score: float  # similarità coseno, 1 = identico
    citation: Citation


class MeshFile(BaseModel):
    mesh_file: str
    region: str | None
    structures: int


class MeshNode(BaseModel):
    """Un nodo del GLB e la struttura che un click su di esso seleziona."""

    fma_id: str = Field(pattern=FMA_PATTERN)
    label_en: str
    label_la: str | None
    label_it: str | None
    system: str | None
    tissue: str | None  # 'skin' | 'muscle' | 'bone': il livello della scena
    focus_fma_id: str = Field(pattern=FMA_PATTERN)
    focus_label_en: str
    focus_label_it: str | None


class SourceRelease(BaseModel):
    source: str
    title: str
    version: str
    url: str
    license: str
    attribution: str
