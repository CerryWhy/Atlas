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
    InheritedLink,
    Phenotype,
    Reading,
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


def _fma_url(fma_id: str) -> str:
    return "http://purl.org/sig/ont/fma/fma" + fma_id.removeprefix("FMA:")


def _inherited_link(
    conn: sqlite3.Connection, label: str, fma_id: str, link: sqlite3.Row
) -> InheritedLink:
    """Un legame ereditato porta due fonti: chi dichiara la sottoclasse (con lato ⊑ senza
    lato, oppure struttura ⊑ … ⊑ antenato) e il termine UBERON più generale a cui le
    fonti cliniche si agganciano."""
    unsided = str(link["unsided_label"] or link["uberon_id"])
    if link["basis"] == "fma_is_a":
        relation = _release_citation(
            conn,
            "fma",
            _fma_url(fma_id),
            f"FMA: {label} discende per sottoclasse da {unsided} ({link['via_id']})",
        )
    elif link["basis"] == "fma_laterality":
        relation = _release_citation(
            conn, "fma", _fma_url(fma_id), f"FMA: {label} è sottoclasse di {unsided}"
        )
    else:
        relation = _release_citation(
            conn,
            "uberon",
            _obo_purl(link["via_id"]),
            f"UBERON: {link['via_label']} is_a {unsided}",
        )
    target = _release_citation(
        conn, "uberon", _obo_purl(link["uberon_id"]), f"UBERON: {unsided} ({link['uberon_id']})"
    )
    return InheritedLink(
        uberon_id=link["uberon_id"],
        basis=link["basis"],
        unsided_label=unsided,
        carries_content=bool(link["carries_content"]),
        citations=[relation, target],
    )


READINGS_LIMIT = 40

_LINK_TEXT = {
    "anatomy_title": "Tratta questa struttura",
    "mesh_anatomy": "Tratta questa struttura (MeSH)",
    "disease_site": "Tramite la malattia",
    "disease_site_part": "Tramite la malattia, in una sua parte",
    "container": "Dalla struttura che la contiene",
    "container_class": "Dalla classe più generale a cui appartiene",
}


def _reading(r: sqlite3.Row) -> Reading:
    """Un documento collegato: la citazione è il documento stesso, con la sua licenza;
    `link` dice perché è collegato (per i legami tramite malattia, quale)."""
    link = _LINK_TEXT.get(r["basis"], r["basis"])
    if r["basis"].startswith("disease_site"):
        link += f": {r['via_label'] or r['via']}"
    elif r["basis"] in ("container", "container_class"):
        link += f": {r['via']}"  # "Liver (FMA:7197)"
    return Reading(
        doc_id=r["doc_id"],
        source=r["source"],
        title=r["title"],
        basis=r["basis"],
        relevance=r["relevance"],
        link=link,
        citation=Citation(
            source=r["source"],
            title=r["title"],
            url=r["url"],
            version=r["retrieved"],
            license=r["license"],
        ),
    )


def _site_citation(conn: sqlite3.Connection, d: sqlite3.Row) -> Citation:
    """La fonte che asserisce la sede della malattia (I2): l'assioma MONDO o quello DO."""
    if d["site_source"] == "doid" and d["site_source_id"]:
        return _release_citation(
            conn,
            "doid",
            _obo_purl(d["site_source_id"]),
            f"Disease Ontology: {d['site_source_id']} ha sede in {d['uberon_id']}",
        )
    return _release_citation(
        conn,
        "mondo",
        _obo_purl(d["mondo_id"]),
        f"MONDO: {d['label']} ha sede in {d['uberon_id']}",
    )


@router.get("/structure/{fma_id}", response_model=Structure)
def get_structure(conn: Conn, fma_id: Annotated[str, Path(pattern=FMA_PATTERN)]) -> Structure:
    row = queries.get_structure(conn, fma_id)
    if row is None:
        raise HTTPException(404, f"{fma_id} non presente in atlas.db")

    links = {
        link["uberon_id"]: _inherited_link(conn, row["label_en"], fma_id, link)
        for link in queries.inherited_links(conn, fma_id)
    }

    def via(uberon_id: str, basis: str) -> list[Citation]:
        """Per una voce ereditata: la relazione di sottoclasse che la porta qui."""
        return [] if basis == "xref" else links[uberon_id].citations[:1]

    icd = queries.source_release(conn, "icd11")
    diseases: list[Disease] = []
    seen: set[str] = set()
    for d in queries.diseases_for_structure(conn, fma_id):
        if d["mondo_id"] in seen:  # righe ordinate: il primo percorso è il migliore
            continue
        seen.add(d["mondo_id"])
        cites = [_site_citation(conn, d)]
        if d["site_source"] == "doid":
            cites.append(
                _release_citation(conn, "mondo", _obo_purl(d["mondo_id"]), f"MONDO: {d['label']}")
            )
        if d["icd11_code"] and icd is not None:
            cites.append(
                _release_citation(
                    conn, "icd11", icd["url"], f"ICD-11 MMS {icd['version']}: {d['icd11_code']}"
                )
            )
        cites += via(d["uberon_id"], d["basis"])
        diseases.append(
            Disease(
                mondo_id=d["mondo_id"],
                label=d["label"],
                icd11_code=d["icd11_code"],
                inherited=d["basis"] != "xref",
                citations=cites,
            )
        )

    phenotypes: list[Phenotype] = []
    seen = set()
    for p in queries.phenotypes_for_structure(conn, fma_id):
        if p["hpo_id"] in seen:
            continue
        seen.add(p["hpo_id"])
        phenotypes.append(
            Phenotype(
                hpo_id=p["hpo_id"],
                label=p["label"],
                inherited=p["basis"] != "xref",
                citations=[
                    _release_citation(
                        conn,
                        "hpo",
                        _obo_purl(p["hpo_id"]),
                        f"HPO: {p['label']} ha sede in {p['uberon_id']}",
                    ),
                    *via(p["uberon_id"], p["basis"]),
                ],
            )
        )

    citations = [
        _release_citation(
            conn,
            "fma",
            _fma_url(fma_id),
            f"FMA: {row['label_en']}",
        )
    ]
    if row["label_it_source"] == "wikidata" and row["label_it_ref"]:
        citations.append(
            _release_citation(
                conn,
                "wikidata",
                f"https://www.wikidata.org/wiki/{row['label_it_ref']}",
                f"Wikidata: nome italiano «{row['label_it']}» ({row['label_it_ref']})",
            )
        )
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
        inherited_from=list(links.values()),
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
        documents=[
            _reading(r) for r in queries.documents_for_structure(conn, fma_id, READINGS_LIMIT)
        ],
    )
