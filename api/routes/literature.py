"""GET /structure/{fma_id}/literature: articoli open access di Europe PMC (tier 2)."""

import re
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from api import queries
from api.db import get_conn
from api.models import FMA_PATTERN, Article, Citation, Literature
from api.retrieval import europepmc

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

_SIDE = re.compile(r"^(right|left)\s+", re.IGNORECASE)


@router.get("/structure/{fma_id}/literature", response_model=Literature)
def literature(
    conn: Conn,
    fma_id: Annotated[str, Path(pattern=FMA_PATTERN)],
    n: Annotated[int, Query(ge=1, le=25)] = 10,
) -> Literature:
    row = queries.get_structure(conn, fma_id)
    if row is None:
        raise HTTPException(404, f"{fma_id} non presente in atlas.db")
    # la letteratura parla di "kidney", non di "right kidney"
    name = _SIDE.sub("", str(row["label_en"])).strip()
    try:
        total, articles = europepmc.search(name, n)
    except europepmc.LiteratureUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return Literature(
        query=europepmc.query_for(name),
        total=total,
        articles=[
            Article(
                id=a.id,
                title=a.title,
                authors=a.authors,
                journal=a.journal,
                year=a.year,
                doi=a.doi,
                citation=Citation(
                    source="europepmc",
                    title=a.title,
                    url=a.url,
                    version=a.year or "",
                    license=a.license,
                ),
            )
            for a in articles
        ],
    )
