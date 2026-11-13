import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from api import queries
from api.db import get_conn
from api.models import MeshFile, MeshNode

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


@router.get("/regions", response_model=list[MeshFile])
def get_regions(conn: Conn) -> list[MeshFile]:
    return [MeshFile(**dict(r)) for r in queries.mesh_files(conn)]


@router.get("/regions/{mesh_file}/nodes", response_model=list[MeshNode])
def get_region_nodes(
    conn: Conn, mesh_file: Annotated[str, Path(pattern=r"^[a-z0-9_]+\.glb$")]
) -> list[MeshNode]:
    rows = queries.mesh_nodes(conn, mesh_file)
    if not rows:
        raise HTTPException(404, f"{mesh_file} non presente in atlas.db")
    return [MeshNode(**dict(r)) for r in rows]
