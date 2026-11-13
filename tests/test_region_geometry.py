"""Le regole geometriche che decidono cosa entra in una regione."""

import importlib

import numpy as np
import trimesh

from pipeline.lib.bp3d import Bp3dTree

build = importlib.import_module("pipeline.02_build_meshes")


def test_is_above_a_horizontal_sheet() -> None:
    sheet = trimesh.Trimesh(
        vertices=[[-1, 1.0, -1], [1, 1.0, -1], [1, 1.0, 1], [-1, 1.0, 1]],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )
    assert build.is_above(np.array([0.0, 1.5, 0.0]), sheet)  # sopra
    assert not build.is_above(np.array([0.0, 0.5, 0.0]), sheet)  # sotto
    assert not build.is_above(np.array([5.0, 1.5, 0.0]), sheet)  # fuori dalla proiezione


def test_fraction_inside() -> None:
    box = (np.zeros(3), np.ones(3))
    pts = np.array([[0.5, 0.5, 0.5], [2, 2, 2], [0.1, 0.9, 0.2], [-1, 0, 0]])
    assert build.fraction_inside(pts, box) == 0.5


def test_owner_is_the_most_specific_concept() -> None:
    t = Bp3dTree()
    t.parent = {"FMA:2": "FMA:1", "FMA:3": "FMA:2"}
    t.elements.update({"FMA:1": {"a", "b", "c"}, "FMA:2": {"a", "b"}, "FMA:3": {"a"}})
    assert build.owner_of("a", ["FMA:1", "FMA:2", "FMA:3"], t) == "FMA:3"
    assert build.owner_of("b", ["FMA:1", "FMA:2"], t) == "FMA:2"
