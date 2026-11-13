"""02 — OBJ BodyParts3D → un GLB (Draco) per regione, centroidi e raggi.

Modello geometrico:
- L'atomo di geometria è l'elemento FJ*.obj. Un concetto FMA è un insieme di elementi,
  e gli insiemi si sovrappongono (un segmento epatico è anche "fegato").
- Ogni elemento va in UNA regione (config.REGIONS: regole per concetto o per volume;
  ciò che nessuna regola reclama segue l'elemento reclamato più vicino).
- Nel GLB un elemento compare una volta, sotto il concetto più specifico che lo contiene
  (meno elementi, poi più profondo). Così i nodi non si sovrappongono e ognuno si chiama
  con un FMA ID reale (I1).
- Un nodo non viene mai spezzato tra due GLB: va nella regione che ospita la maggioranza
  dei suoi elementi. Un FMA ID compare quindi in un solo file.
- Centroide e raggio di OGNI concetto (anche quelli senza nodo proprio, es. "fegato")
  vengono dal box dell'unione dei suoi elementi: sono il bersaglio della camera.

Output: data/meshes/<regione>.glb e data/build/geometry.json (letto da 03).
Idempotente: salta se gli output esistono e la tabella config.REGIONS non è cambiata,
salvo --force.

Uso:  python -m pipeline.02_build_meshes [--force]
"""

import argparse
import json
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

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


def elements_under(tree: bp3d.Bp3dTree, concept: str) -> set[str]:
    """Elementi del concetto e di tutte le sue parti."""
    out: set[str] = set()
    stack = [concept]
    while stack:
        node = stack.pop()
        out |= tree.elements.get(node, set())
        stack.extend(tree.children.get(node, []))
    return out


def assign_to_nearest(
    unclaimed: list[str], claimed: dict[str, str], centers: dict[str, np.ndarray]
) -> dict[str, str]:
    """Ogni elemento non reclamato segue la regione dell'elemento reclamato più vicino
    (distanza tra i centri del box). Deterministico: a parità vince l'ID più basso."""
    if not unclaimed:
        return {}
    keys = sorted(claimed)
    tree = cKDTree(np.array([centers[k] for k in keys]))
    _, idx = tree.query(np.array([centers[k] for k in unclaimed]))
    return {fj: claimed[keys[i]] for fj, i in zip(unclaimed, idx, strict=True)}


def assign_regions(
    tree: bp3d.Bp3dTree,
    meshes: dict[str, trimesh.Trimesh],
    bounds: dict[str, Box],
    rules: tuple[config.RegionRule, ...],
) -> dict[str, str]:
    """elemento → chiave di regione, per tutti gli elementi."""
    centers = {fj: (b[0] + b[1]) / 2 for fj, b in bounds.items()}
    claimed: dict[str, str] = {}
    for rule in rules:
        candidates: set[str] = set()
        for concept in rule.concepts:
            candidates |= elements_under(tree, concept)
        if rule.box_fma:
            box = union([bounds[fj] for fj in tree.elements[rule.box_fma]])
            ceiling: trimesh.Trimesh | None = None
            ceiling_fjs: set[str] = set()
            if rule.ceiling_fma:
                ceiling_fjs = elements_under(tree, rule.ceiling_fma)
                joined = trimesh.util.concatenate([meshes[fj] for fj in sorted(ceiling_fjs)])
                assert isinstance(joined, trimesh.Trimesh)
                ceiling = joined
            for fj, m in meshes.items():
                if fraction_inside(m.vertices, box) < config.ELEMENT_MIN_FRACTION:
                    continue
                if ceiling is None or fj in ceiling_fjs or not is_above(centers[fj], ceiling):
                    candidates.add(fj)
        for fj in sorted(candidates):
            claimed.setdefault(fj, rule.key)
    unclaimed = sorted(set(bounds) - set(claimed))
    claimed.update(assign_to_nearest(unclaimed, dict(claimed), centers))
    return claimed


def plurality(regions: list[str], order: tuple[str, ...]) -> tuple[str, float]:
    """Regione più frequente e la sua quota; a parità vince la prima nell'ordine di config."""
    counts = Counter(regions)
    best = max(counts, key=lambda r: (counts[r], -order.index(r)))
    return best, counts[best] / len(regions)


def build_nodes(
    tree: bp3d.Bp3dTree, element_region: dict[str, str], order: tuple[str, ...]
) -> dict[str, dict[str, list[str]]]:
    """regione → {concetto proprietario → elementi}. Un nodo non si spezza tra regioni."""
    concepts_of: dict[str, list[str]] = defaultdict(list)
    for concept, els in tree.elements.items():
        for fj in els:
            concepts_of[fj].append(concept)
    owned: dict[str, list[str]] = defaultdict(list)
    for fj in sorted(element_region):
        owned[owner_of(fj, concepts_of[fj], tree)].append(fj)
    out: dict[str, dict[str, list[str]]] = {key: {} for key in order}
    for concept, fjs in sorted(owned.items()):
        region, _ = plurality([element_region[f] for f in fjs], order)
        out[region][concept] = fjs
    return out


def regions_signature() -> str:
    return json.dumps(
        [
            [r.key, list(r.concepts), r.box_fma, r.ceiling_fma, config.ELEMENT_MIN_FRACTION]
            for r in config.REGIONS
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    signature = regions_signature()
    if config.GEOMETRY_JSON.exists() and not args.force:
        done = json.loads(config.GEOMETRY_JSON.read_text("utf-8"))
        files_ok = all((config.MESHES / r["mesh_file"]).exists() for r in done["regions"].values())
        if done.get("signature") == signature and files_ok:
            print(f"  = {len(done['regions'])} GLB già presenti (--force per rifare)")
            return 0

    tree = bp3d.load_tree()
    all_fj = sorted(set().union(*tree.elements.values()))
    print(f"  carico {len(all_fj)} elementi OBJ…")
    meshes = mesh.load_each(config.BP3D_ZIP, all_fj)
    bounds = element_bounds(meshes)

    order = config.REGION_KEYS
    element_region = assign_regions(tree, meshes, bounds, config.REGIONS)
    nodes_by_region = build_nodes(tree, element_region, order)

    concepts: dict[str, dict[str, float | int | str]] = {}
    for concept, els in tree.elements.items():
        lo, hi = union([bounds[fj] for fj in els])
        c = (lo + hi) / 2
        region, share = plurality([element_region[f] for f in els], order)
        concepts[concept] = {
            "cx": float(c[0]),
            "cy": float(c[1]),
            "cz": float(c[2]),
            "radius": float(np.linalg.norm(hi - lo) / 2),
            "elements": len(els),
            "region": region,
            "region_share": share,
        }

    config.MESHES.mkdir(parents=True, exist_ok=True)
    cli = mesh.find_gltf_transform(config.ROOT)
    regions_out: dict[str, dict[str, object]] = {}
    for key in order:
        nodes = nodes_by_region[key]
        if not nodes:
            print(f"  {key}: nessun nodo, regione saltata")
            continue
        glb_name = f"{key}.glb"
        node_meshes = {
            fma_id: trimesh.util.concatenate([meshes[fj] for fj in fjs])
            for fma_id, fjs in nodes.items()
        }
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.glb"
            mesh.export_glb(node_meshes, raw)  # type: ignore[arg-type]
            mesh.draco_compress(raw, config.MESHES / glb_name, cli)
        n_el = sum(len(f) for f in nodes.values())
        kb = (config.MESHES / glb_name).stat().st_size // 1024
        print(f"  {key:<11} {len(nodes):4} nodi, {n_el:4} elementi, {kb:6} KB")
        regions_out[key] = {"mesh_file": glb_name, "nodes": nodes}

    stale = {p.name for p in config.MESHES.glob("*.glb")} - {
        str(r["mesh_file"]) for r in regions_out.values()
    }
    for name in sorted(stale):
        (config.MESHES / name).unlink()
        print(f"  rimosso {name} (non più prodotto da config.REGIONS)")

    config.BUILD.mkdir(parents=True, exist_ok=True)
    config.GEOMETRY_JSON.write_text(
        json.dumps({"signature": signature, "regions": regions_out, "concepts": concepts}),
        encoding="utf-8",
    )
    total = sum(len(nodes_by_region[k]) for k in regions_out)
    print(f"OK: {total} nodi in {len(regions_out)} GLB, geometria di {len(concepts)} concetti")
    return 0


if __name__ == "__main__":
    # gli zip di BodyParts3D sono grandi: verifichiamo subito che ci siano
    if not zipfile.is_zipfile(config.BP3D_ZIP):
        sys.exit(f"{config.BP3D_ZIP} mancante o corrotto: eseguire 01_fetch_sources")
    sys.exit(main())
