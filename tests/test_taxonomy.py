from pipeline.lib import taxonomy

# Right fourth rib ⊑ Fourth rib ⊑ Rib ⊑ Bone organ ⊑ Organ
SUPERS = {
    "FMA:1": {"FMA:2"},  # Right fourth rib → Fourth rib
    "FMA:2": {"FMA:3"},  # Fourth rib → Rib
    "FMA:3": {"FMA:4"},  # Rib → Bone organ
    "FMA:4": {"FMA:5"},  # Bone organ → Organ
    "FMA:6": {"FMA:3"},  # Fifth rib → Rib
    "FMA:7": {"FMA:2", "FMA:8"},  # due superclassi alla stessa distanza
    "FMA:8": {"FMA:5"},
}
NAMES = {
    "FMA:1": "Right fourth rib",
    "FMA:2": "Fourth rib",
    "FMA:3": "Rib",
    "FMA:4": "Bone organ",
    "FMA:5": "Organ",
    "FMA:8": "Flat bone",
}
BY_FMA = {
    "FMA:2": ["UBERON:0000002"],  # fourth rib: esiste ma senza contenuto clinico
    "FMA:3": ["UBERON:0002228"],  # rib
    "FMA:4": ["UBERON:0001474"],  # bone element
    "FMA:5": ["UBERON:0000062"],  # organ
    "FMA:8": ["UBERON:0000008"],
}
CLINICAL = {"UBERON:0002228", "UBERON:0001474", "UBERON:0000062", "UBERON:0000008"}


def _links(fma_id: str, *, by_fma=BY_FMA, max_hops=3, max_desc=100):  # type: ignore[no-untyped-def]
    count = taxonomy.subclass_counter(SUPERS, cap=max_desc)
    return taxonomy.nearest_described_ancestors(
        fma_id, SUPERS, NAMES, by_fma, CLINICAL, count, max_hops, max_desc
    )


def test_climbs_to_the_nearest_ancestor_with_clinical_content() -> None:
    [link] = _links("FMA:1")
    # "Fourth rib" ha un termine UBERON ma nessun contenuto: si sale fino a "Rib"
    assert (link.ancestor_id, link.uberon_id, link.hops) == ("FMA:3", "UBERON:0002228", 2)
    assert link.ancestor_label == "Rib"


def test_stops_at_max_hops() -> None:
    assert _links("FMA:1", max_hops=1) == []


def test_too_generic_ancestors_are_refused() -> None:
    # con soglia 2, "Rib" (4 sottoclassi: 1, 2, 6, 7) è già troppo generico
    assert _links("FMA:1", max_desc=2) == []


def test_ambiguous_xref_is_refused() -> None:
    by_fma = {**BY_FMA, "FMA:3": ["UBERON:0002228", "UBERON:0009999"]}
    links = _links("FMA:1", by_fma=by_fma, max_desc=1000)
    # "Rib" è ambiguo: si sale al livello successivo, "Bone organ"
    assert [(link.ancestor_id, link.hops) for link in links] == [("FMA:4", 3)]


def test_all_valid_ancestors_at_the_same_distance_are_kept() -> None:
    links = _links("FMA:7")
    assert [link.ancestor_id for link in links] == ["FMA:8"]  # FMA:2 non porta contenuto
    links = _links("FMA:7", by_fma={**BY_FMA, "FMA:2": ["UBERON:0002228"]})
    assert [link.ancestor_id for link in links] == ["FMA:2", "FMA:8"]


def test_two_ancestors_with_the_same_uberon_term_give_one_link() -> None:
    by_fma = {**BY_FMA, "FMA:2": ["UBERON:0000008"]}
    links = _links("FMA:7", by_fma=by_fma)
    assert [(link.ancestor_id, link.uberon_id) for link in links] == [("FMA:2", "UBERON:0000008")]


def test_subclass_counter_stops_at_cap() -> None:
    count = taxonomy.subclass_counter(SUPERS, cap=2)
    assert count("FMA:2") == 2  # Right fourth rib, FMA:7
    assert count("FMA:5") > 2  # oltre il tetto il conteggio si ferma: basta sapere che è > 2
    assert count("FMA:1") == 0
