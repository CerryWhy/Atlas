import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from api import queries
from api.db import get_conn
from api.models import MeshFile

router = APIRouter()


@router.get("/regions", response_model=list[MeshFile])
def get_regions(conn: Annotated[sqlite3.Connection, Depends(get_conn)]) -> list[MeshFile]:
    return [MeshFile(**dict(r)) for r in queries.mesh_files(conn)]
