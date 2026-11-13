from pathlib import Path

from pipeline.lib import laterality, obo

NAMES = {
    "FMA:1": "Humerus",
    "FMA:2": "Long bone",
    "FMA:3": "Gastric artery",
    "FMA:4": "Side of heart",
    "FMA:5": "humerus",
}


def test_unsided_name() -> None:
    assert laterality.unsided_name("Right humerus") == "humerus"
    assert laterality.unsided_name("left  Lower lobe of lung") == "lower lobe of lung"
    assert laterality.unsided_name("Humerus") is None
    assert laterality.unsided_name("Rightward thing") is None


def test_inherits_only_from_a_declared_parent_with_the_same_name() -> None:
    assert laterality.unsided_parent("Right humerus", ["FMA:1", "FMA:2"], NAMES) == "FMA:1"
    # il genitore giusto esiste ma non è dichiarato come superclasse: niente eredità
    assert laterality.unsided_parent("Right humerus", ["FMA:2"], NAMES) is None


def test_names_with_a_side_that_are_not_sided_variants_do_not_inherit() -> None:
    # "Left gastric artery" è un'arteria a sé: il suo genitore non si chiama "gastric artery"
    assert laterality.unsided_parent("Left gastric artery", ["FMA:2"], NAMES) is None
    # "Right side of heart" non è un "side of heart" con lato
    assert laterality.unsided_parent("Right side of heart", ["FMA:2"], NAMES) is None


def test_ambiguous_parents_are_refused() -> None:
    assert laterality.unsided_parent("Right humerus", ["FMA:1", "FMA:5"], NAMES) is None


def test_obo_reads_is_a(tmp_path: Path) -> None:
    p = tmp_path / "u.obo"
    p.write_text(
        "format-version: 1.2\n\n[Term]\nid: UBERON:0004539\nname: right kidney\n"
        "is_a: UBERON:0002113 ! kidney\n",
        encoding="utf-8",
    )
    t = obo.load_terms(p)["UBERON:0004539"]
    assert t.is_a == ["UBERON:0002113"]
