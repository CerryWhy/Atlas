from pipeline.lib import phenosite

IS_A = {
    "HP:3": {"HP:2"},  # Back pain ⊑ Abnormality of the vertebral column
    "HP:2": {"HP:1"},  # ⊑ Phenotypic abnormality
    "HP:5": {"HP:4"},  # Gingivitis ⊑ Abnormal gingiva morphology
    "HP:9": {"HP:1"},  # un fenotipo senza sede tra gli antenati
}
SITES = phenosite.own_sites(
    {
        "HP:2": [("inheres_in", "UBERON:0001130"), ("qualifier", "PATO:0000460")],
        "HP:4": [("inheres_in_part_of", "UBERON:0001828")],  # gingiva
        "HP:7": [("inheres_in", "UBERON:0002107"), ("towards", "UBERON:0000000")],
    }
)
BY_UBERON = {
    "UBERON:0001130": {"FMA:13478"},  # vertebral column
    "UBERON:0000165": {"FMA:49184"},  # mouth
    "UBERON:0002107": {"FMA:7197"},  # liver
    "UBERON:0000916": {"FMA:9577"},  # abdomen (larga)
}
PART_OF = {"UBERON:0001828": {"UBERON:0000165"}, "UBERON:0002107": {"UBERON:0000916"}}


def test_own_sites_keep_only_site_relations() -> None:
    assert SITES == {
        "HP:2": {"UBERON:0001130"},
        "HP:4": {"UBERON:0001828"},
        "HP:7": {"UBERON:0002107"},
    }


def test_a_symptom_without_a_site_inherits_the_nearest_ancestors() -> None:
    assert phenosite.phenotype_sites("HP:3", IS_A, SITES) == [("UBERON:0001130", "HP:2", 1)]
    assert phenosite.phenotype_sites("HP:7", IS_A, SITES) == [("UBERON:0002107", "HP:7", 0)]
    assert phenosite.phenotype_sites("HP:9", IS_A, SITES) == []


def test_a_site_out_of_the_scene_climbs_to_the_whole() -> None:
    assert phenosite.site_structures("UBERON:0001828", BY_UBERON, PART_OF, frozenset()) == [
        ("FMA:49184", 1)
    ]
    # il fegato è in scena: non si sale all'addome
    assert phenosite.site_structures("UBERON:0002107", BY_UBERON, PART_OF, frozenset()) == [
        ("FMA:7197", 0)
    ]
    # risalendo non si arriva a una struttura larga
    gone = {"UBERON:0002107": set()}
    assert phenosite.site_structures("UBERON:0002107", gone, PART_OF, frozenset({"FMA:9577"})) == []


def test_loci_say_how_they_were_found() -> None:
    got = phenosite.loci(
        ["HP:3", "HP:5", "HP:7", "HP:9"], IS_A, SITES, BY_UBERON, PART_OF, frozenset()
    )
    assert [(x.hpo_id, x.fma_id, x.basis, x.via_hpo, x.hops) for x in got] == [
        ("HP:3", "FMA:13478", "inherited", "HP:2", 1),
        ("HP:5", "FMA:49184", "inherited", "HP:4", 2),  # 1 passo in HPO + 1 in UBERON
        ("HP:7", "FMA:7197", "logical", "HP:7", 0),
    ]
