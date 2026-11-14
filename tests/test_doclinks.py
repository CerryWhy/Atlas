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


def test_structures_without_documents_borrow_from_their_container() -> None:
    from dataclasses import replace

    v = replace(
        V,
        structures_by_uberon={
            **V.structures_by_uberon,
            "UBERON:0001114": {"FMA:13362"},  # lobo destro del fegato
            "UBERON:0001157": {"FMA:14546"},  # colon trasverso
        },
        structure_parent={"FMA:13362": "FMA:7197", "FMA:14546": "FMA:71131"},
        broad=frozenset({"FMA:71131"}),  # tratto gastrointestinale: troppo largo
        uberon_is_a={"UBERON:0001157": {"UBERON:0000168"}},
        uberon_part_of={**V.uberon_part_of, "UBERON:0000168": {"UBERON:0001155"}},
        labels={"FMA:7197": "Liver", "UBERON:0001155": "colon"},
    )
    refs = [*REFS, ("medlineplus:2", "MESH", "D003108")]
    v = replace(v, uberon_by_mesh={**v.uberon_by_mesh, "MESH:D003108": "UBERON:0001155"})
    _, structures = doclinks.link(refs, TITLES, v)
    got = {(d, f): (r, b, via) for d, f, r, b, via in structures}
    # il lobo destro (senza documenti propri) prende quelli diretti del fegato
    assert got[("statpearls:article-1", "FMA:13362")] == (0.3, "container", "Liver (FMA:7197)")
    # il colon trasverso: in scena il genitore è troppo largo; via UBERON is_a + part_of,
    # quindi "classe", non "contenitore"
    assert got[("medlineplus:2", "FMA:14546")] == (
        0.3,
        "container_class",
        "colon (UBERON:0001155)",
    )


def test_generic_uberon_terms_are_not_containers() -> None:
    from dataclasses import replace

    v = replace(
        V,
        structures_by_uberon={**V.structures_by_uberon, "UBERON:0001157": {"FMA:14546"}},
        uberon_is_a={"UBERON:0001157": {"UBERON:0001155"}},
        uberon_generic=frozenset({"UBERON:0001155"}),
        uberon_by_mesh={**V.uberon_by_mesh, "MESH:D003108": "UBERON:0001155"},
    )
    _, structures = doclinks.link([("medlineplus:2", "MESH", "D003108")], {}, v)
    assert ("medlineplus:2", "FMA:14546") not in {(d, f) for d, f, *_ in structures}


def _container_vocab(**kw):  # type: ignore[no-untyped-def]
    """Una struttura FMA:100 (UBERON:100) senza documenti, nel mezzo di gerarchie di prova."""
    from dataclasses import replace

    base = replace(
        V,
        structures_by_uberon={"UBERON:100": {"FMA:100"}},
        disease_sites={},
        uberon_part_of={},
        structure_parent={},
        broad=frozenset(),
        labels={},
    )
    return replace(base, **kw)


def _containers(v):  # type: ignore[no-untyped-def]
    refs = [(f"doc:{u}", "MESH", f"D{u[-3:]}") for u in ("UBERON:200", "UBERON:300", "UBERON:400")]
    v = __import__("dataclasses").replace(
        v, uberon_by_mesh={f"MESH:D{u[-3:]}": u for u in ("UBERON:200", "UBERON:300", "UBERON:400")}
    )
    _, structures = doclinks.link(refs, {}, v)
    return {(d, f): (b, via) for d, f, _r, b, via in structures if f == "FMA:100"}


def test_a_uberon_term_of_a_broad_structure_is_not_a_container() -> None:
    """Il freno sulle strutture larghe vale anche quando ci si arriva da UBERON."""
    v = _container_vocab(
        structures_by_uberon={"UBERON:100": {"FMA:100"}, "UBERON:200": {"FMA:9577"}},
        broad=frozenset({"FMA:9577"}),  # "abdomen"
        uberon_part_of={"UBERON:100": {"UBERON:200"}},
    )
    assert _containers(v) == {}


def test_broad_structures_do_not_borrow_documents() -> None:
    v = _container_vocab(
        broad=frozenset({"FMA:100"}), uberon_part_of={"UBERON:100": {"UBERON:200"}}
    )
    assert _containers(v) == {}


def test_container_climb_stops_after_max_hops() -> None:
    chain = {
        "UBERON:100": {"UBERON:150"},
        "UBERON:150": {"UBERON:170"},
        "UBERON:170": {"UBERON:200"},
    }
    assert doclinks.MAX_CONTAINER_HOPS == 2
    assert _containers(_container_vocab(uberon_part_of=chain)) == {}
    short = {"UBERON:100": {"UBERON:150"}, "UBERON:150": {"UBERON:200"}}
    assert _containers(_container_vocab(uberon_part_of=short)) == {
        ("doc:UBERON:200", "FMA:100"): ("container", "UBERON:200 (UBERON:200)")
    }


def test_part_of_wins_over_is_a_at_the_same_distance() -> None:
    v = _container_vocab(
        uberon_part_of={"UBERON:100": {"UBERON:300"}},
        uberon_is_a={"UBERON:100": {"UBERON:200"}},
    )
    assert _containers(v) == {
        ("doc:UBERON:300", "FMA:100"): ("container", "UBERON:300 (UBERON:300)")
    }


def test_container_documents_keep_the_most_relevant_first() -> None:
    """Il taglio a MAX_CONTAINER_DOCS tiene i documenti più pertinenti, non i primi in
    ordine alfabetico: il capitolo di anatomia prima delle pagine sulle malattie."""
    from dataclasses import replace

    n = doclinks.MAX_CONTAINER_DOCS + 5
    v = replace(
        _container_vocab(uberon_part_of={"UBERON:100": {"UBERON:200"}}),
        uberon_by_name={"colon": "UBERON:200"},
        diseases={f"MONDO:{i:07d}" for i in range(n)},
        mondo_by_xref={f"MESH:C{i}": f"MONDO:{i:07d}" for i in range(n)},
        disease_sites={f"MONDO:{i:07d}": {"UBERON:200"} for i in range(n)},
    )
    refs = [(f"a:{i:02d}", "MESH", f"C{i}") for i in range(n)]
    refs.append(("z:anatomy", "anatomy", "Colon"))
    _, structures = doclinks.link(refs, {}, v)
    docs = {d for d, f, *_ in structures if f == "FMA:100"}
    assert len(docs) == doclinks.MAX_CONTAINER_DOCS
    assert "z:anatomy" in docs  # pur essendo ultimo in ordine alfabetico


def test_structures_with_any_link_get_no_container() -> None:
    """Anche un legame debole (sede di una malattia in una parte) basta: niente contenitore."""
    v = _container_vocab(
        uberon_part_of={"UBERON:100": {"UBERON:200"}},
        structures_by_uberon={"UBERON:100": {"FMA:100"}, "UBERON:050": set()},
    )
    v = __import__("dataclasses").replace(
        v,
        diseases={"MONDO:0000001"},
        mondo_by_xref={"MESH:C1": "MONDO:0000001"},
        disease_sites={"MONDO:0000001": {"UBERON:100"}},
    )
    _, structures = doclinks.link([("d", "MESH", "C1")], {}, v)
    assert {b for _d, f, _r, b, _v in structures if f == "FMA:100"} == {"disease_site"}


def test_generic_terms_block_big_categories_and_systems() -> None:
    import importlib

    m = importlib.import_module("pipeline.06_link_documents")
    cap = doclinks.MAX_CONTAINER_SUBCLASSES
    is_a = {f"UBERON:{i}": {"UBERON:1"} for i in range(10, 10 + cap + 1)}  # 1: troppe
    is_a |= {"UBERON:2": {"UBERON:3"}, "UBERON:4": {"UBERON:5"}, "UBERON:6": {"UBERON:4"}}
    names = {"UBERON:5": "anatomical system", "UBERON:4": "digestive system"}
    generic = m.generic_terms(is_a, names)
    assert "UBERON:1" in generic
    assert {"UBERON:5", "UBERON:4", "UBERON:6"} <= generic  # il sistema e le sue sottoclassi
    assert "UBERON:3" not in generic and "UBERON:2" not in generic


def test_variants_for_parentheses_and_latin_plurals() -> None:
    assert doclinks.singular("thoracic vertebrae") == "thoracic vertebra"
    assert doclinks.singular("aorta") == "aorta"  # non è un plurale
    assert doclinks.name_variants("Portal Venous System (Hepatic Portal System)") == [
        "portal venous system (hepatic portal system)",
        "portal venous system",
        "hepatic portal system",
    ]
    assert doclinks.name_variants("Adrenal Glands (Suprarenal Glands)") == [
        "adrenal glands (suprarenal glands)",
        "adrenal glands",
        "adrenal gland",
        "suprarenal glands",
        "suprarenal gland",
    ]
