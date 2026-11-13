"""BodyParts3D OBJ → GLB.

BodyParts3D usa millimetri e asse Z verso l'alto. Nel GLB convertiamo in metri e
in Y verso l'alto (convenzione glTF), così centroide e raggio salvati in
`structure` vivono nello stesso spazio della scena.

Il nodo glTF si chiama con l'FMA ID (I1) e porta l'ID anche in `extras.fma_id`:
three.js sanifica i nomi dei nodi (rimuove ':'), `extras` arriva intatto in userData.
"""

import io
import json
import struct
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

MM_TO_M = 0.001
# Z-up → Y-up: (x, y, z) → (x, z, -y)
Z_UP_TO_Y_UP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=np.float64)


@dataclass(frozen=True)
class Geometry:
    cx: float
    cy: float
    cz: float
    radius: float


def load_elements(zip_path: Path, element_ids: list[str]) -> trimesh.Trimesh:
    """Carica e fonde gli elementi FJ*.obj che compongono una struttura."""
    with zipfile.ZipFile(zip_path) as zf:
        index = {Path(n).stem: n for n in zf.namelist() if n.lower().endswith(".obj")}
        missing = [e for e in element_ids if e not in index]
        if missing:
            raise FileNotFoundError(f"Elementi assenti nell'archivio: {missing}")
        parts = []
        for eid in element_ids:
            data = zf.read(index[eid])
            loaded = trimesh.load(io.BytesIO(data), file_type="obj", force="mesh", process=False)
            parts.append(loaded)
    merged = trimesh.util.concatenate(parts)
    assert isinstance(merged, trimesh.Trimesh)
    merged.merge_vertices()
    merged.apply_scale(MM_TO_M)  # type: ignore[no-untyped-call]
    merged.apply_transform(Z_UP_TO_Y_UP)
    return merged


def geometry_of(mesh: trimesh.Trimesh) -> Geometry:
    lo, hi = mesh.bounds
    center = (lo + hi) / 2.0
    radius = float(np.linalg.norm(hi - lo) / 2.0)
    return Geometry(float(center[0]), float(center[1]), float(center[2]), radius)


def export_glb(meshes: dict[str, trimesh.Trimesh], out: Path) -> None:
    """Scrive un GLB con un nodo per struttura, nome = fma_id, extras.fma_id = fma_id."""
    scene = trimesh.Scene()
    for fma_id, mesh in meshes.items():
        scene.add_geometry(mesh, node_name=fma_id, geom_name=fma_id)
    glb = scene.export(file_type="glb", include_normals=True)  # type: ignore[no-untyped-call]
    assert isinstance(glb, bytes)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_inject_fma_extras(glb))


def _inject_fma_extras(glb: bytes) -> bytes:
    """Aggiunge extras.fma_id a ogni nodo nominato, riscrivendo il chunk JSON."""
    magic, version, _ = struct.unpack_from("<4sII", glb, 0)
    assert magic == b"glTF" and version == 2
    json_len, json_type = struct.unpack_from("<I4s", glb, 12)
    assert json_type == b"JSON"
    doc = json.loads(glb[20 : 20 + json_len])
    rest = glb[20 + json_len :]
    for node in doc.get("nodes", []):
        name = node.get("name", "")
        if name.startswith("FMA:"):
            node.setdefault("extras", {})["fma_id"] = name
    payload = json.dumps(doc, separators=(",", ":")).encode()
    payload += b" " * ((4 - len(payload) % 4) % 4)
    total = 12 + 8 + len(payload) + len(rest)
    return (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<I4s", len(payload), b"JSON")
        + payload
        + rest
    )


def draco_compress(src: Path, dst: Path, cli: list[str]) -> None:
    """Compressione Draco via gltf-transform (CLI Node, dev-dependency del repo)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([*cli, "draco", str(src), str(dst)], check=True)
