"""GET /search: ricerca vettoriale sul corpus locale (tier 1). Ogni risultato porta la
citazione del suo documento (I2)."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.db import get_conn
from api.models import Citation, SearchHit
from api.retrieval import local

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


@router.get("/search", response_model=list[SearchHit])
def search(
    conn: Conn,
    q: Annotated[str, Query(min_length=2, max_length=500)],
    k: Annotated[int, Query(ge=1, le=50)] = 8,
) -> list[SearchHit]:
    try:
        rows = local.search(conn, q, k)
    except local.SearchUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return [
        SearchHit(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            text=r["text"],
            score=round(1.0 - float(r["distance"]), 4),
            citation=Citation(
                source=r["source"],
                title=r["title"],
                url=r["url"],
                version=r["retrieved"],
                license=r["license"],
            ),
        )
        for r in rows
    ]
