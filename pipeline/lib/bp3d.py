"""Lettura delle tabelle BodyParts3D (albero PART-OF, derivato da FMA)."""

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.lib import config


def to_curie(bp3d_id: str) -> str:
    """'FMA7197' → 'FMA:7197'."""
    if not bp3d_id.startswith("FMA") or not bp3d_id[3:].isdigit():
        raise ValueError(f"ID BodyParts3D inatteso: {bp3d_id!r}")
    return f"FMA:{bp3d_id[3:]}"


def _rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    return [[c.strip() for c in r] for r in rows[1:] if r]


@dataclass
class Bp3dTree:
    labels: dict[str, str] = field(default_factory=dict)  # fma_id → label BP3D
    parent: dict[str, str] = field(default_factory=dict)  # fma_id → parent fma_id
    children: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    elements: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))  # → FJ ids

    def depth(self, fma_id: str) -> int:
        d = 0
        while fma_id in self.parent:
            fma_id = self.parent[fma_id]
            d += 1
        return d

    def ancestors(self, fma_id: str) -> list[str]:
        out = []
        while fma_id in self.parent:
            fma_id = self.parent[fma_id]
            out.append(fma_id)
        return out


def load_tree() -> Bp3dTree:
    t = Bp3dTree()
    for r in _rows(config.BP3D_PARTS):
        t.labels[to_curie(r[0])] = r[2]
    for r in _rows(config.BP3D_TREE):
        parent, child = to_curie(r[0]), to_curie(r[2])
        if child in t.parent and t.parent[child] != parent:
            raise ValueError(f"{child} ha due genitori nell'albero PART-OF")
        t.parent[child] = parent
        t.children[parent].append(child)
    for r in _rows(config.BP3D_ELEMENTS):
        t.elements[to_curie(r[0])].add(r[2])
    return t
