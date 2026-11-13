"""02 — OBJ BodyParts3D → GLB di regione (Draco), centroidi e raggi.

Modello geometrico:
- L'atomo di geometria è l'elemento FJ*.obj. Un concetto FMA è un insieme di elementi,
  e gli insiemi si sovrappongono (un segmento epatico è anche "fegato").
- Il confine di regione è geometrico: un elemento è nella regione se la maggior parte
  dei suoi vertici cade nel box del concetto di confine (config.REGION_BOUNDARY_FMA) e,
  dove è definito un tetto (config.REGION_CEILING_FMA, il diaframma), se il suo centro
  non poggia sopra quella superficie. Il tetto toglie cuore e basi polmonari dall'addome.
- Nel GLB ogni elemento della regione compare UNA volta, sotto il concetto più
  specifico che lo contiene (meno elementi, poi più profondo). Così i nodi non si
  sovrappongono e ognuno si chiama con un FMA ID reale (I1).
- Centroide e raggio di OGNI concetto (anche quelli senza nodo proprio, es. "fegato")
  vengono dal box dell'unione dei suoi elementi: sono il bersaglio della camera.

Output: data/meshes/<regione>.glb e data/build/geometry.json (letto da 03).
Idempotente: salta se gli output esistono, salvo --force.

Uso:  python -m pipeline.02_build_meshes [--force]
"""

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import trimesh

from pipeline.lib import bp3d, config, mesh

Box = tuple[np.ndarray, np.ndarray]


def element_bounds(meshes: dict[str, trimesh.Trimesh]) -> dict[str, Box]:
    return {fj: (m.bounds[0].copy(), m.bounds[1].copy()) for fj, m in meshes.items()}


def union(boxes: list[Box]) -> Box:
    return (
        np.min([b[0] for b in boxes], axis=0),
        np.max([b[1] for b in boxes], axis=0),
    )


def fraction_inside(vertices: np.ndarray, box: Box) -> float:
    ok = np.all((vertices >= box[0]) & (vertices <= box[1]), axis=1)
    return float(ok.mean())


def is_above(point: np.ndarray, surface: trimesh.Trimesh) -> bool:
    """True se il punto poggia sopra la superficie: un raggio verticale verso il basso
    la incontra. (Sotto la cupola del diaframma, o dietro i suoi pilastri, non accade.)"""
    tri = surface.triangles  # (T, 3, 3)
    a, b, c = tri[:, 0, [0, 2]], tri[:, 1, [0, 2]], tri[:, 2, [0, 2]]
    p = point[[0, 2]]
    v0, v1, v2 = b - a, c - a, p - a
    den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / den
        v = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / den
        hit = (den != 0) & (u >= 0) & (v >= 0) & (u + v <= 1)
    if not hit.any():
        return False
    y = (
        tri[hit, 0, 1]
        + u[hit] * (tri[hit, 1, 1] - tri[hit, 0, 1])
        + v[hit] * (tri[hit, 2, 1] - tri[hit, 0, 1])
    )
    return bool((y <= point[1]).any())


def owner_of(fj: str, containing: list[str], tree: bp3d.Bp3dTree) -> str:
    """Il concetto più specifico che contiene l'elemento."""
    return min(containing, key=lambda c: (len(tree.elements[c]), -tree.depth(c), c))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    region = config.ACTIVE_REGION
    glb_name = f"{region}.glb"
    glb_path = config.MESHES / glb_name
    if glb_path.exists() and config.GEOMETRY_JSON.exists() and not args.force:
        print(f"  = {glb_name} e {config.GEOMETRY_JSON.name} già presenti (--force per rifare)")
        return 0

    tree = bp3d.load_tree()
    all_fj = sorted(set().union(*tree.elements.values()))
    print(f"  carico {len(all_fj)} elementi OBJ…")
    meshes = mesh.load_each(config.BP3D_ZIP, all_fj)
    bounds = element_bounds(meshes)

    boundary = config.REGION_BOUNDARY_FMA[region]
    region_box = union([bounds[fj] for fj in tree.elements[boundary]])
    ceiling_fma = config.REGION_CEILING_FMA.get(region)
    ceiling: trimesh.Trimesh | None = None
    if ceiling_fma:
        joined = trimesh.util.concatenate([meshes[fj] for fj in sorted(tree.elements[ceiling_fma])])
        assert isinstance(joined, trimesh.Trimesh)
        ceiling = joined
    ceiling_fjs = tree.elements[ceiling_fma] if ceiling_fma else set()
    in_region = set()
    for fj, m in meshes.items():
        if fraction_inside(m.vertices, region_box) < config.ELEMENT_MIN_FRACTION:
            continue
        center = (bounds[fj][0] + bounds[fj][1]) / 2
        if ceiling is None or fj in ceiling_fjs or not is_above(center, ceiling):
            in_region.add(fj)
    print(f"  box {region} ({boundary}): {region_box[0].round(3)} → {region_box[1].round(3)}")
    print(f"  elementi nella regione: {len(in_region)}/{len(all_fj)}")

    # appartenenza elemento → concetti
    concepts_of: dict[str, list[str]] = {}
    for concept, els in tree.elements.items():
        for fj in els:
            concepts_of.setdefault(fj, []).append(concept)

    nodes: dict[str, list[str]] = {}
    for fj in sorted(in_region):
        nodes.setdefault(owner_of(fj, concepts_of[fj], tree), []).append(fj)

    concepts: dict[str, dict[str, float | int]] = {}
    for concept, els in tree.elements.items():
        lo, hi = union([bounds[fj] for fj in els])
        c = (lo + hi) / 2
        concepts[concept] = {
            "cx": float(c[0]),
            "cy": float(c[1]),
            "cz": float(c[2]),
            "radius": float(np.linalg.norm(hi - lo) / 2),
            "elements": len(els),
            "region_fraction": len(els & in_region) / len(els),
        }

    node_meshes = {
        fma_id: trimesh.util.concatenate([meshes[fj] for fj in fjs])
        for fma_id, fjs in nodes.items()
    }
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.glb"
        mesh.export_glb(node_meshes, raw)  # type: ignore[arg-type]
        mesh.draco_compress(raw, glb_path, mesh.find_gltf_transform(config.ROOT))

    config.BUILD.mkdir(parents=True, exist_ok=True)
    config.GEOMETRY_JSON.write_text(
        json.dumps(
            {
                "region": region,
                "mesh_file": glb_name,
                "region_box": [region_box[0].tolist(), region_box[1].tolist()],
                "nodes": nodes,
                "concepts": concepts,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    kb = glb_path.stat().st_size // 1024
    print(f"OK: {len(nodes)} nodi in {glb_name} ({kb} KB), geometria di {len(concepts)} concetti")
    return 0


if __name__ == "__main__":
    # gli zip di BodyParts3D sono grandi: verifichiamo subito che ci siano
    if not zipfile.is_zipfile(config.BP3D_ZIP):
        sys.exit(f"{config.BP3D_ZIP} mancante o corrotto: eseguire 01_fetch_sources")
    sys.exit(main())
