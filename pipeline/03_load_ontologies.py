"""03 — Ontologie → tabelle structure / phenotype / disease e relazioni.

Cosa viene da dove:
- structure           BodyParts3D (concetti, albero PART-OF derivato da FMA) + FMA 5.x
                      (nome preferito, equivalenti latino/italiano con lingua dichiarata)
                      + geometria calcolata da 02 (data/build/geometry.json)
                      + nomi italiani da Wikidata dove FMA non li ha (P1402, uno a uno).
- phenotype           HPO (hp-full.obo).
- phenotype_structure definizioni logiche HPO: inheres_in / inheres_in_part_of → UBERON.
- disease             MONDO; icd11_code dall'xref equivalente icd11.foundation risolto
                      sulla Simple Tabulation WHO.
- disease_phenotype   HPOA (aspetto P, senza qualificatore NOT), OMIM/ORPHA → MONDO
                      via xref equivalenti.
- disease_structure   assiomi di sede: Disease Ontology (RO:0004026, DOID → MONDO via
                      xref equivalenti) + MONDO (disease_has_location e affini).

`structure.uberon_id` NON viene toccato: è dello script 04.
Idempotente: UPSERT sulle entità, sostituzione delle tabelle di relazione.
Nessun ID viene costruito: ciò che non si trova finisce in `unmapped` (I5).

Uso:  python -m pipeline.03_load_ontologies
"""

import csv
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict

from pipeline.lib import bp3d, config, db, fetch, laterality, obo, owl, wikidata

# Figli diretti di "human body" nell'albero BodyParts3D che sono sistemi → chiave `system`.
# Gli ID vengono dal file; la chiave è una nostra etichetta di classificazione.
SYSTEM_ROOTS = {
    "FMA:7152": "digestive",
    "FMA:7157": "nervous",
    "FMA:7158": "respiratory",
    "FMA:7159": "urinary",
    "FMA:7160": "genital",
    "FMA:7161": "cardiovascular",
    "FMA:228642": "cardiovascular",
    "FMA:7482": "musculoskeletal",
    "FMA:9668": "endocrine",
    "FMA:72979": "integumentary",
    "FMA:74657": "integumentary",
    "FMA:79063": "fascial",
}

HPO_SITE_RELATIONS = {"inheres_in", "inheres_in_part_of"}
BILATERAL_WORD = re.compile(r"\bbilateral(ly)?\b", re.IGNORECASE)
MONDO_SITE_RELATIONS = {
    "disease_has_location",
    "disease_has_inflammation_site",
    "disease_arises_from_structure",
}
DO_HAS_LOCATION = "http://purl.obolibrary.org/obo/RO_0004026"

LICENSES = {
    "http://creativecommons.org/licenses/by/4.0/": "CC BY 4.0",
    "http://creativecommons.org/licenses/by/3.0/": "CC BY 3.0",
    "https://creativecommons.org/publicdomain/zero/1.0/": "CC0 1.0",
    "https://hpo.jax.org/app/license": "HPO License",
}

OWNED_UNMAPPED = [
    "bp3d_not_in_fma",
    "parent_not_direct_fma_part",
    "hpoa_no_mondo",
    "hpoa_unknown_hpo",
    "doid_no_mondo",
]


# ─── structure ──────────────────────────────────────────────────────────────
def load_structures(conn: sqlite3.Connection) -> tuple[str, list[tuple[object, ...]]]:
    tree = bp3d.load_tree()
    geometry = json.loads(config.GEOMETRY_JSON.read_text("utf-8"))
    # nodo (FMA ID) → file GLB che lo ospita; un nodo sta in un solo file
    node_file: dict[str, str] = {
        fma_id: region["mesh_file"]
        for region in geometry["regions"].values()
        for fma_id in region["nodes"]
    }
    geo: dict[str, dict[str, float | str]] = geometry["concepts"]

    fma, fma_version, fma_part_of = owl.read_fma(config.FMA_OWL, set(tree.labels))
    wd_labels, wd_stats = wikidata.parse_sparql(config.WIKIDATA_LABELS_IT)
    unmapped: list[tuple[object, ...]] = []
    rows: list[dict[str, object]] = []
    for fma_id, bp_label in tree.labels.items():
        cls = fma.get(fma_id)
        if cls is None or not (cls.preferred_name or cls.label):
            unmapped.append(("bp3d_not_in_fma", fma_id, bp_label, f"assente in FMA {fma_version}"))
        parent = tree.parent.get(fma_id)
        if cls is not None and parent is not None and parent not in cls.part_of:
            unmapped.append(
                (
                    "parent_not_direct_fma_part",
                    fma_id,
                    bp_label,
                    f"BodyParts3D: parte di {parent}; FMA non lo asserisce come parte diretta",
                )
            )
        ancestors = [fma_id, *tree.ancestors(fma_id)]
        system = next((SYSTEM_ROOTS[a] for a in ancestors if a in SYSTEM_ROOTS), None)
        if system is None:
            # l'albero di BodyParts3D colloca molte parti sotto una regione (testa, torace):
            # l'apparato lo dichiara FMA, risalendo il suo part_of
            whole = owl.nearest_whole(fma_id, fma_part_of, set(SYSTEM_ROOTS))
            system = SYSTEM_ROOTS[whole] if whole else None
        g = geo.get(fma_id)
        # regione di un concetto: quella che ospita la maggioranza dei suoi elementi, se
        # ne ospita abbastanza; i concetti diffusi (un intero apparato) restano senza.
        region = (
            str(g["region"])
            if g is not None and float(g["region_share"]) >= config.REGION_MIN_FRACTION
            else None
        )
        equivalents = cls.equivalents if cls else {}
        label_en = ((cls.preferred_name or cls.label) if cls else None) or bp_label
        # nome italiano: prima FMA, poi Wikidata (solo legami uno a uno, vedi wikidata.py)
        it_fma = next(iter(equivalents.get("Italian", [])), None)
        it_wd = wd_labels.get(fma_id)
        label_it, it_source, it_ref = (
            (it_fma, "fma", None)
            if it_fma
            else (it_wd.label, "wikidata", it_wd.qid)
            if it_wd
            else (None, None, None)
        )
        rows.append(
            {
                "fma_id": fma_id,
                "label_en": label_en,
                "label_la": next(iter(equivalents.get("Latin", [])), None),
                "label_it": label_it,
                "label_it_source": it_source,
                "label_it_ref": it_ref,
                "sided": int(laterality.unsided_name(label_en) is not None),
                "parent_fma_id": parent,
                "system": system,
                "region": region,
                "depth": tree.depth(fma_id),
                "mesh_file": node_file.get(fma_id),
                "mesh_node": fma_id if fma_id in node_file else None,
                "cx": g["cx"] if g else None,
                "cy": g["cy"] if g else None,
                "cz": g["cz"] if g else None,
                "radius": g["radius"] if g else None,
            }
        )
    # i genitori vanno inseriti prima dei figli (FK su parent_fma_id)
    rows.sort(key=lambda r: (int(str(r["depth"])), str(r["fma_id"])))
    db.upsert_structures(conn, rows)
    per_region = Counter(str(r["region"]) for r in rows if r["region"])
    print(f"  structure: {len(rows)} concetti; per regione: {dict(sorted(per_region.items()))}")
    it_by_source = Counter(str(r["label_it_source"]) for r in rows if r["label_it_source"])
    print(
        f"  nomi italiani: {dict(sorted(it_by_source.items()))} su {len(rows)};"
        f" Wikidata scartati per ambiguità: {wd_stats.fma_on_many_items} FMA su più voci,"
        f" {wd_stats.item_with_many_fma} voci con più FMA"
    )
    return fma_version, unmapped


# ─── phenotype ──────────────────────────────────────────────────────────────
def bilateral_ids(terms: list[obo.Term]) -> set[str]:
    """Fenotipi che HPO dichiara bilaterali: il nome contiene la parola "bilateral",
    oppure la definizione logica usa il modificatore "Bilateral" (cercato per nome nel
    file, non scritto qui: I5). Un fenotipo bilaterale non descrive una struttura con
    un solo lato ("Right kidney" non ha una "Bilateral renal agenesis")."""
    modifiers = {t.id for t in terms if t.name.strip().lower() == "bilateral"}
    return {
        t.id
        for t in terms
        if BILATERAL_WORD.search(t.name) or any(target in modifiers for _, target in t.relations)
    }


def load_phenotypes(conn: sqlite3.Connection) -> set[str]:
    terms = [t for t in obo.iter_terms(config.HPO_OBO) if t.id.startswith("HP:") and not t.obsolete]
    bilateral = bilateral_ids(terms)
    db.upsert_phenotypes(
        conn, [(t.id, t.name, t.definition, int(t.id in bilateral)) for t in terms]
    )
    links = {
        (t.id, target)
        for t in terms
        for rel, target in t.relations
        if rel in HPO_SITE_RELATIONS and target.startswith("UBERON:")
    }
    db.replace_phenotype_structure(conn, sorted(links))
    print(
        f"  phenotype: {len(terms)} termini ({len(bilateral)} bilaterali),"
        f" {len(links)} legami fenotipo → sede"
    )
    return {t.id for t in terms}


# ─── disease ────────────────────────────────────────────────────────────────
def icd11_foundation_to_code() -> dict[str, str]:
    """Foundation entity id → codice MMS, dalla Simple Tabulation WHO."""
    out: dict[str, str] = {}
    with config.ICD11_TABULATION.open(encoding="utf-8-sig") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if len(row) < 3 or not row[0].startswith("http://id.who.int/icd/entity/"):
                continue
            if code := row[2].strip():
                out[row[0].rsplit("/", 1)[1]] = code
    return out


def load_diseases(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Carica MONDO; restituisce xref equivalente (OMIM:…, Orphanet:…, DOID:…) → MONDO ID."""
    foundation = icd11_foundation_to_code()
    rows: list[tuple[object, ...]] = []
    site_links: set[tuple[str, str]] = set()
    by_xref: dict[str, list[str]] = defaultdict(list)
    with_icd = 0
    for t in obo.iter_terms(config.MONDO_OBO):
        if not t.id.startswith("MONDO:") or t.obsolete:
            continue
        codes = {
            foundation[x.split(":", 1)[1]]
            for x in t.equivalent_xrefs
            if x.startswith("icd11.foundation:") and x.split(":", 1)[1] in foundation
        }
        code = codes.pop() if len(codes) == 1 else None  # ambiguo → nessun codice
        with_icd += code is not None
        rows.append((t.id, t.name, code, t.definition))
        for x in t.equivalent_xrefs:
            by_xref[x].append(t.id)
        site_links.update(
            (t.id, target)
            for rel, target in t.relations
            if rel in MONDO_SITE_RELATIONS and target.startswith("UBERON:")
        )
    db.upsert_diseases(conn, rows)
    print(f"  disease: {len(rows)} termini MONDO, {with_icd} con codice ICD-11 MMS")
    load_disease_structure(conn, site_links, by_xref, {str(r[0]) for r in rows})
    return by_xref


def load_disease_structure(
    conn: sqlite3.Connection,
    mondo_links: set[tuple[str, str]],
    by_xref: dict[str, list[str]],
    mondo_ids: set[str],
) -> None:
    # (malattia, sede) → chi lo asserisce: serve a citare la sede (I2). MONDO prima, poi DO.
    links: dict[tuple[str, str], tuple[str, str]] = {
        pair: ("mondo", pair[0]) for pair in sorted(mondo_links)
    }
    unmapped: list[tuple[object, ...]] = []
    from_do = 0
    for doid, target in owl.read_restrictions(config.DOID_OWL, DO_HAS_LOCATION, "DOID"):
        if not target.startswith("UBERON:"):
            continue
        targets = [m for m in by_xref.get(doid, []) if m in mondo_ids]
        if len(targets) != 1:
            unmapped.append(("doid_no_mondo", doid, None, f"{len(targets)} equivalenti MONDO"))
            continue
        pair = (targets[0], target)
        if pair not in links:
            from_do += 1
            links[pair] = ("doid", doid)
    db.replace_disease_structure(
        conn, [(m, u, src, src_id) for (m, u), (src, src_id) in sorted(links.items())]
    )
    db.replace_unmapped(conn, ["doid_no_mondo"], sorted(set(unmapped), key=str))
    print(
        f"  disease_structure: {len(links)} legami "
        f"({len(mondo_links)} da MONDO, +{from_do} solo da Disease Ontology)"
    )


def load_disease_phenotype(
    conn: sqlite3.Connection, by_xref: dict[str, list[str]], hpo_ids: set[str]
) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    unmapped: dict[tuple[str, str], tuple[object, ...]] = {}
    skipped: Counter[str] = Counter()
    with config.HPOA.open(encoding="utf-8") as fh:
        reader = csv.DictReader((line for line in fh if not line.startswith("#")), delimiter="\t")
        for r in reader:
            if r["aspect"] != "P" or r["qualifier"] == "NOT":
                skipped["non_P_o_NOT"] += 1
                continue
            db_id = r["database_id"].replace("ORPHA:", "Orphanet:")
            targets = by_xref.get(db_id, [])
            if len(targets) != 1:
                unmapped[("hpoa_no_mondo", r["database_id"])] = (
                    "hpoa_no_mondo",
                    r["database_id"],
                    r["disease_name"],
                    f"{len(targets)} equivalenti MONDO",
                )
                continue
            if r["hpo_id"] not in hpo_ids:
                unmapped[("hpoa_unknown_hpo", r["hpo_id"])] = (
                    "hpoa_unknown_hpo",
                    r["hpo_id"],
                    None,
                    "assente o obsoleto in hp-full.obo",
                )
                continue
            rows.append((targets[0], r["hpo_id"], r["frequency"] or None))
    db.replace_disease_phenotype(conn, rows)
    print(f"  disease_phenotype: {len(rows)} annotazioni HPOA caricate, {dict(skipped)}")
    return list(unmapped.values())


# ─── fonti ──────────────────────────────────────────────────────────────────
def hpoa_version() -> str:
    with config.HPOA.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#version:"):
                return line.split(":", 1)[1].strip()
            if not line.startswith("#"):
                break
    raise LookupError("phenotype.hpoa senza #version")


def register_sources(conn: sqlite3.Connection, fma_version: str) -> None:
    def lic(path: object) -> str:
        return LICENSES[obo.license_url(path)]  # type: ignore[arg-type]

    mondo_lic, uberon_lic, hpo_lic = (
        lic(config.MONDO_OBO),
        lic(config.UBERON_OBO),
        lic(config.HPO_OBO),
    )
    icd = config.ICD11_RELEASE_FILE.read_text(encoding="utf-8").strip()
    hpo_url = "https://hpo.jax.org/app/license"
    sources = [
        (
            "bodyparts3d",
            "BodyParts3D",
            "4.0 (LATEST)",
            "https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html",
            "CC BY 4.0",  # dichiarata alla pagina lic.html del Licensor
            "BodyParts3D, © The Database Center for Life Science, "
            "licensed under CC Attribution 4.0 International.",
        ),
        (
            "fma",
            "Foundational Model of Anatomy",
            fma_version,
            "http://si.washington.edu/projects/fma",
            "CC BY 4.0",  # file LICENSE nella cartella di release
            "Foundational Model of Anatomy ontology, Structural Informatics Group, "
            "University of Washington, licensed under CC BY 4.0.",
        ),
        (
            "uberon",
            "Uberon multi-species anatomy ontology",
            obo.data_version(config.UBERON_OBO),
            "https://obophenotype.github.io/uberon/",
            uberon_lic,
            f"Uberon anatomy ontology, licensed under {uberon_lic}.",
        ),
        (
            "hpo",
            "Human Phenotype Ontology",
            obo.data_version(config.HPO_OBO),
            "https://hpo.jax.org/",
            hpo_lic,
            f"Human Phenotype Ontology, Monarch Initiative, under the HPO license ({hpo_url}).",
        ),
        (
            "hpoa",
            "HPO Annotations (phenotype.hpoa)",
            hpoa_version(),
            "https://hpo.jax.org/data/annotations",
            hpo_lic,
            f"HPO disease–phenotype annotations, used under the HPO license ({hpo_url}).",
        ),
        (
            "mondo",
            "Mondo Disease Ontology",
            obo.data_version(config.MONDO_OBO),
            "https://mondo.monarchinitiative.org/",
            mondo_lic,
            f"Mondo Disease Ontology, Monarch Initiative, licensed under {mondo_lic}.",
        ),
        (
            "doid",
            "Human Disease Ontology",
            owl.ontology_version(config.DOID_OWL),
            "https://disease-ontology.org/",
            "CC0 1.0",  # dichiarata nell'header del file
            "Human Disease Ontology, Institute for Genome Sciences, University of Maryland "
            "(CC0 1.0).",
        ),
        (
            "icd11",
            "ICD-11 for Mortality and Morbidity Statistics",
            icd,
            f"https://icd.who.int/browse/{icd}/mms/en",
            "CC BY-ND 3.0 IGO",  # documento WHO icd11-license.pdf
            f"ICD-11 MMS {icd}, World Health Organization, licensed under CC BY-ND 3.0 IGO. "
            "Codes reproduced without modification.",
        ),
        (
            "wikidata",
            "Wikidata (Italian labels of items with an FMA ID, P1402)",
            fetch.retrieved(config.WIKIDATA_LABELS_IT),
            "https://www.wikidata.org/wiki/Property:P1402",
            "CC0 1.0",  # https://www.wikidata.org/wiki/Wikidata:Licensing (dati strutturati)
            "Italian anatomical names from Wikidata, available under CC0 1.0.",
        ),
    ]
    for s in sources:
        db.upsert_source_release(conn, *s)


def main() -> int:
    if not config.GEOMETRY_JSON.exists():
        sys.exit("manca data/build/geometry.json: eseguire prima 02_build_meshes")
    conn = db.connect(config.DB_PATH)
    with conn:
        db.migrate(conn)
        fma_version, unmapped = load_structures(conn)
        hpo_ids = load_phenotypes(conn)
        by_xref = load_diseases(conn)
        unmapped += load_disease_phenotype(conn, by_xref, hpo_ids)
        db.replace_unmapped(conn, [k for k in OWNED_UNMAPPED if k != "doid_no_mondo"], unmapped)
        register_sources(conn, fma_version)
    for kind, n in db.unmapped_counts(conn):
        print(f"  unmapped[{kind}] = {n}")
    conn.close()
    print("OK: ontologie caricate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
