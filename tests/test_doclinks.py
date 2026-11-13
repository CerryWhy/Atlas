from pipeline.lib import doclinks

V = doclinks.Vocab(
    mondo_by_xref={"MESH:D008107": "MONDO:0005154", "Orphanet:141": "MONDO:0010079"},
    mondo_by_name={"canavan disease": "MONDO:0010079", "hepatitis b": "MONDO:0005344"},
    diseases={"MONDO:0005154", "MONDO:0010079", "MONDO:0005344", "MONDO:0011778"},
    uberon_by_mesh={"MESH:D008099": "UBERON:0002107"},
    uberon_by_name={"calcaneus": "UBERON:0001450", "liver": "UBERON:0002107"},
    fma_by_name={"liver": "FMA:7197"},
    structures_by_uberon={
        "UBERON:0002107": {"FMA:7197"},
        "UBERON:0001450": {"FMA:24496", "FMA:24497"},
        "UBERON:0001898": {"FMA:62004"},
    },
    disease_sites={
        "MONDO:0005154": {"UBERON:0002107"},
        "MONDO:0010079": {"UBERON:0001898"},
        "MONDO:0005344": {"UBERON:0004647"},  # sede: lobulo epatico, non in scena
    },
    uberon_part_of={"UBERON:0004647": {"UBERON:0002107"}},
)
TITLES = {
    "medlineplus:1": ("medlineplus", "Liver Diseases"),
    "orphanet:141": ("orphanet", "Canavan disease"),
    "statpearls:article-1": ("statpearls", "Anatomy, Abdomen and Pelvis, Liver"),
    "statpearls:article-2": ("statpearls", "Anatomy, Bony Pelvis and Lower Limb: Calcaneus"),
    "statpearls:article-3": ("statpearls", "Hepatitis B"),
    "statpearls:article-4": ("statpearls", "Hepatitis B Vaccine Guidelines"),
}
REFS = [
    ("medlineplus:1", "MESH", "D008107"),
    ("medlineplus:1", "MESH", "D008099"),
    ("orphanet:141", "Orphanet", "141"),
    ("orphanet:141", "MONDO", "MONDO:0010079"),
    ("statpearls:article-1", "anatomy", "Liver"),
    ("statpearls:article-2", "anatomy", "Calcaneus"),
]


def test_diseases_come_from_declared_codes_or_exact_titles() -> None:
    diseases, _ = doclinks.link(REFS, TITLES, V)
    got = {(d, m, b) for d, m, b, _via in diseases}
    assert got == {
        ("medlineplus:1", "MONDO:0005154", "mondo_xref_mesh"),
        ("orphanet:141", "MONDO:0010079", "mondo_xref_orphanet"),  # stesso legame: il primo
        ("statpearls:article-3", "MONDO:0005344", "title_exact"),
    }
    # "Hepatitis B Vaccine Guidelines" non è il nome di una malattia: nessun legame


def test_structures_keep_the_strongest_link() -> None:
    _, structures = doclinks.link(REFS, TITLES, V)
    got = {(d, f): (r, b) for d, f, r, b, _via in structures}
    assert got[("statpearls:article-1", "FMA:7197")] == (1.0, "anatomy_title")
    # "Calcaneus" non è un nome FMA in scena: via UBERON arriva a destro e sinistro
    assert got[("statpearls:article-2", "FMA:24496")] == (1.0, "anatomy_title")
    assert got[("statpearls:article-2", "FMA:24497")] == (1.0, "anatomy_title")
    # MeSH anatomico (0.8) vince sulla sede della malattia (0.5) per lo stesso fegato
    assert got[("medlineplus:1", "FMA:7197")] == (0.8, "mesh_anatomy")
    # dalla malattia alla sede
    assert got[("orphanet:141", "FMA:62004")] == (0.5, "disease_site")


def test_unknown_mondo_ids_are_not_linked() -> None:
    diseases, _ = doclinks.link([("orphanet:9", "MONDO", "MONDO:9999999")], {}, V)
    assert diseases == []


def test_unique_index_drops_ambiguous_keys() -> None:
    assert doclinks.unique_index([("a", "1"), ("a", "2"), ("b", "3"), ("b", "3")]) == {"b": "3"}
    assert doclinks.norm("  Liver  Diseases. ") == "liver diseases"


def test_disease_in_a_part_reaches_the_whole() -> None:
    _, structures = doclinks.link(REFS, TITLES, V)
    got = {(d, f): (r, b) for d, f, r, b, _via in structures}
    # epatite B ha sede nel lobulo epatico, che è part_of fegato
    assert got[("statpearls:article-3", "FMA:7197")] == (0.4, "disease_site_part")


def test_anatomy_title_variants() -> None:
    assert doclinks.singular("subclavian arteries") == "subclavian artery"
    assert doclinks.singular("radius") == "radius"
    assert doclinks.singular("pelvis") == "pelvis"
    assert doclinks.name_variants("Foot Talus") == ["foot talus", "talus"]
    assert doclinks.name_variants("Knee") == ["knee"]
    # si toglie solo una regione: "Lumbosacral Trunk" non è un "trunk"
    assert doclinks.name_variants("Lumbosacral Trunk") == ["lumbosacral trunk"]
    refs = [("statpearls:article-9", "anatomy", "Foot Calcaneus")]
    _, structures = doclinks.link(refs, {}, V)
    assert {(f, via) for _d, f, _r, _b, via in structures} == {
        ("FMA:24496", "calcaneus"),
        ("FMA:24497", "calcaneus"),
    }


def test_climbing_part_of_never_lands_on_broad_structures() -> None:
    from dataclasses import replace

    v = replace(V, broad=frozenset({"FMA:7197"}))
    _, structures = doclinks.link(REFS, TITLES, v)
    assert ("statpearls:article-3", "FMA:7197") not in {(d, f) for d, f, *_ in structures}
    # ma una sede esatta resta, anche se larga
    assert ("medlineplus:1", "FMA:7197") in {(d, f) for d, f, *_ in structures}
