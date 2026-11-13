import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from api import queries
from api.db import get_conn
from api.models import SourceRelease

router = APIRouter()


@router.get("/attribution", response_model=list[SourceRelease])
def get_attribution(
    conn: Annotated[sqlite3.Connection, Depends(get_conn)],
) -> list[SourceRelease]:
    return [SourceRelease(**dict(r)) for r in queries.source_releases(conn)]
