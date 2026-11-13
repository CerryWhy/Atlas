import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from api import queries
from api.db import get_conn
from api.models import (
    FMA_PATTERN,
    ChildRef,
    Citation,
    Disease,
    Phenotype,
    Structure,
    StructureRef,
)

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

    phenotypes = [
        Phenotype(
            hpo_id=p["hpo_id"],
            label=p["label"],
            citations=[
                _release_citation(conn, "hpo", _obo_purl(p["hpo_id"]), f"HPO: {p['label']}")
            ],
        )
        for p in queries.phenotypes_for_structure(conn, fma_id)
    ]

    citations = [
        _release_citation(
            conn,
            "fma",
            "http://purl.org/sig/ont/fma/fma" + fma_id.removeprefix("FMA:"),
            f"FMA: {row['label_en']}",
        )
    ]
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
        ancestors=[StructureRef(**dict(a)) for a in queries.ancestors(conn, fma_id)],
        children=[
            ChildRef(
                fma_id=c["fma_id"],
                label_en=c["label_en"],
                label_it=c["label_it"],
                has_uberon=bool(c["has_uberon"]),
            )
            for c in queries.children(conn, fma_id)
        ],
        mesh_nodes=queries.mesh_nodes_under(conn, fma_id),
        diseases=diseases,
        phenotypes=phenotypes,
    )
