"""Modelli di risposta. Lo schema OpenAPI generato da qui è la fonte dei tipi TS."""

from pydantic import BaseModel, Field

FMA_PATTERN = r"^FMA:\d+$"
MONDO_PATTERN = r"^MONDO:\d{7}$"


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
    citations: list[Citation] = Field(min_length=1)


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
    diseases: list[Disease]


class MeshFile(BaseModel):
    mesh_file: str
    region: str | None
    structures: int


class SourceRelease(BaseModel):
    source: str
    title: str
    version: str
    url: str
    license: str
    attribution: str
