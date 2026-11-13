import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from api import queries
from api.db import get_conn
from api.models import FMA_PATTERN, Citation, Disease, Structure

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def _release_citation(conn: sqlite3.Connection, source: str, url: str, title: str) -> Citation:
    rel = queries.source_release(conn, source)
    if rel is None:
        raise HTTPException(500, f"Fonte '{source}' non registrata in atlas.db")
    return Citation(
        source=source, title=title, url=url, version=rel["version"], license=rel["license"]
    )


def _obo_purl(curie: str) -> str:
    return "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


@router.get("/structure/{fma_id}", response_model=Structure)
def get_structure(conn: Conn, fma_id: Annotated[str, Path(pattern=FMA_PATTERN)]) -> Structure:
    row = queries.get_structure(conn, fma_id)
    if row is None:
        raise HTTPException(404, f"{fma_id} non presente in atlas.db")

    icd = queries.source_release(conn, "icd11")
    diseases = []
    for d in queries.diseases_for_structure(conn, fma_id):
        cites = [_release_citation(conn, "mondo", _obo_purl(d["mondo_id"]), f"MONDO: {d['label']}")]
        if d["icd11_code"] and icd is not None:
            cites.append(
                _release_citation(
                    conn, "icd11", icd["url"], f"ICD-11 MMS {icd['version']}: {d['icd11_code']}"
                )
            )
        diseases.append(
            Disease(
                mondo_id=d["mondo_id"],
                label=d["label"],
                icd11_code=d["icd11_code"],
                citations=cites,
            )
        )

    citations = []
    if row["uberon_id"]:
        citations.append(
            _release_citation(
                conn, "uberon", _obo_purl(row["uberon_id"]), f"UBERON: {row['uberon_id']}"
            )
        )
    citations.append(
        _release_citation(
            conn,
            "bodyparts3d",
            "https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html",
            f"BodyParts3D: {row['fma_id']}",
        )
    )
    has_centroid = row["cx"] is not None
    return Structure(
        fma_id=row["fma_id"],
        label_en=row["label_en"],
        label_la=row["label_la"],
        label_it=row["label_it"],
        uberon_id=row["uberon_id"],
        parent_fma_id=row["parent_fma_id"],
        system=row["system"],
        region=row["region"],
        depth=row["depth"],
        mesh_file=row["mesh_file"],
        mesh_node=row["mesh_node"],
        centroid=(row["cx"], row["cy"], row["cz"]) if has_centroid else None,
        radius=row["radius"],
        citations=citations,
        diseases=diseases,
    )
