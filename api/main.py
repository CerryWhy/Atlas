"""API sottile: API key, CORS, query. Nessuna logica di dominio (SPEC §4)."""

import os
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.db import MESHES_DIR
from api.routes import attribution, literature, locate, regions, search, structure

API_KEY = os.environ.get("ATLAS_API_KEY")


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Se ATLAS_API_KEY è impostata, ogni richiesta API deve presentarla."""
    if API_KEY and not (x_api_key and secrets.compare_digest(x_api_key, API_KEY)):
        raise HTTPException(401, "API key mancante o errata")


app = FastAPI(title="ATLAS API", version="0.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ATLAS_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

guarded = [Depends(require_api_key)]
app.include_router(structure.router, dependencies=guarded)
app.include_router(regions.router, dependencies=guarded)
app.include_router(attribution.router, dependencies=guarded)
app.include_router(search.router, dependencies=guarded)
app.include_router(locate.router, dependencies=guarded)
app.include_router(literature.router, dependencies=guarded)

MESHES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/meshes", StaticFiles(directory=MESHES_DIR), name="meshes")
