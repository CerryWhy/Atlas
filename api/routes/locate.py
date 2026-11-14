"""POST /locate: dal sintomo al corpo (SPEC Fase 5).

testo → embedding (stesso modello di 07, in locale) → fenotipi HPO più vicini →
strutture in scena (phenotype_locus, calcolata da 04) → centroidi e nodi da accendere.
Ogni fenotipo cita HPO, e se la sede è ereditata anche l'antenato che la dichiara (I2).
Il testo non viene salvato né registrato (I4); la risposta descrive dove un segno ha
sede in generale, non cosa abbia una persona (SPEC §9).
"""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from api import queries
from api.db import get_conn
from api.models import Citation, Located, LocatedPhenotype, LocatedStructure, LocateRequest
from api.retrieval import local

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

N_PHENOTYPES = 8  # fenotipi considerati, i più vicini al testo
N_STRUCTURES = 5  # strutture restituite


def _hpo(conn: sqlite3.Connection, hpo_id: str, title: str) -> Citation:
    rel = queries.source_release(conn, "hpo")
    if rel is None:
        raise HTTPException(500, "Fonte 'hpo' non registrata in atlas.db")
    url = "http://purl.obolibrary.org/obo/" + hpo_id.replace(":", "_")
    return Citation(
        source="hpo", title=title, url=url, version=rel["version"], license=rel["license"]
    )


@router.post("/locate", response_model=Located)
def locate(conn: Conn, body: LocateRequest) -> Located:
    try:
        query = local.encode_query(conn, body.text, "phenotype_vec_meta")
    except local.SearchUnavailable as e:
        raise HTTPException(503, str(e)) from e
    nearest = queries.nearest_phenotypes(conn, query, N_PHENOTYPES)
    if not nearest:
        raise HTTPException(503, "nessun fenotipo indicizzato: eseguire pipeline 04 e 07")
    rank = {hpo: i for i, (hpo, _d) in enumerate(nearest)}
    loci = queries.phenotype_loci(conn, [h for h, _d in nearest])

    phenotypes: dict[str, LocatedPhenotype] = {}
    best: dict[str, tuple[int, int, sqlite3.Row]] = {}  # fma → (rango fenotipo, hops, riga)
    pointers: dict[str, list[str]] = {}
    for r in loci:
        hpo, fma = r["hpo_id"], r["fma_id"]
        if hpo not in phenotypes:
            cites = [_hpo(conn, hpo, f"HPO: {r['hpo_label']}")]
            if r["basis"] == "inherited":
                cites.append(
                    _hpo(
                        conn,
                        r["via_hpo"],
                        f"HPO: {r['hpo_label']} è sottoclasse di {r['via_label']},"
                        f" che ha sede in {r['uberon_id']}",
                    )
                )
            dist = dict(nearest)[hpo]
            phenotypes[hpo] = LocatedPhenotype(
                hpo_id=hpo,
                label=r["hpo_label"],
                score=round(1.0 - dist, 4),
                basis=r["basis"],
                via_label=r["via_label"],
                citations=cites,
            )
        pointers.setdefault(fma, []).append(hpo)
        key = (rank[hpo], int(r["hops"]))
        if fma not in best or key < best[fma][:2]:
            best[fma] = (*key, r)

    ordered = sorted(best.items(), key=lambda kv: (kv[1][0], kv[1][1], kv[0]))[:N_STRUCTURES]
    structures = []
    for fma, (_rank, hops, r) in ordered:
        has_centroid = r["cx"] is not None
        structures.append(
            LocatedStructure(
                fma_id=fma,
                label_en=r["label_en"],
                label_it=r["label_it"],
                centroid=(r["cx"], r["cy"], r["cz"]) if has_centroid else None,
                radius=r["radius"],
                mesh_nodes=queries.mesh_nodes_under(conn, fma),
                phenotypes=sorted(set(pointers[fma]), key=lambda h: rank[h]),
                hops=hops,
            )
        )
    used = {h for s in structures for h in s.phenotypes}
    return Located(
        phenotypes=sorted(
            (p for h, p in phenotypes.items() if h in used), key=lambda p: rank[p.hpo_id]
        ),
        structures=structures,
    )
