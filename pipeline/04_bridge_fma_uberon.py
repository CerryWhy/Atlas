"""04 — Crosswalk FMA ↔ UBERON e report delle strutture non mappate.

Il ponte è l'xref `FMA:nnnn` dichiarato sui termini UBERON. Regole:
- esattamente un termine UBERON cita l'FMA ID  → structure.uberon_id
- nessuno                                      → unmapped('fma_no_uberon')
- più di uno                                   → unmapped('fma_multi_uberon'), nessuna scelta
Nessuna deduzione per analogia o per nome (I5): la copertura va misurata, non nascosta.

Ereditarietà destra/sinistra (pipeline/lib/laterality.py): una struttura con lato
("Right humerus") riceve anche il legame UBERON della sua versione senza lato, quando
la fonte dichiara la sottoclasse e i nomi coincidono a meno del lato:
- FMA:   Right humerus ⊑ Humerus,  Humerus ↔ UBERON:0000976 (xref esatto)
- UBERON: right kidney is_a kidney (quando la struttura ha già il termine con lato)
Questi legami vanno in `structure_uberon` con la loro provenienza; `structure.uberon_id`
resta solo l'xref esatto.

Ereditarietà dalla classe più generale (pipeline/lib/taxonomy.py): una struttura che,
dopo i due passi sopra, non ha ancora contenuto clinico riceve il legame dell'antenato
FMA più vicino (catena di rdfs:subClassOf dichiarati) che le fonti cliniche descrivono:
- FMA:   Right fourth rib ⊑ Fourth rib ⊑ Rib,  Rib ↔ UBERON:0002228 (xref esatto)
Limiti in config.ISA_MAX_HOPS e config.ISA_MAX_DESCENDANTS; elenco completo dei legami
in data/reports/is_a_links.md, da leggere per tarare i limiti.

Scrive un report per regione, data/reports/unmapped_<regione>.md, e un riepilogo
data/reports/coverage.md. Vanno letti a ogni esecuzione.
Idempotente: ricalcola e riscrive tutto.

Scrive anche `structure.tissue` (pelle, muscolo, osso) risalendo rdfs:subClassOf fino
alle classi di config.TISSUE_CLASSES: serve ai livelli della scena, non alla clinica.

Uso:  python -m pipeline.04_bridge_fma_uberon
"""

import sys
from collections import Counter, defaultdict

from pipeline.lib import config, db, laterality, obo, owl, taxonomy


def uberon_by_fma() -> tuple[dict[str, list[str]], dict[str, str], dict[str, list[str]]]:
    by_fma: dict[str, list[str]] = defaultdict(list)
    names: dict[str, str] = {}
    is_a: dict[str, list[str]] = {}
    for t in obo.iter_terms(config.UBERON_OBO):
        if t.obsolete or not t.id.startswith("UBERON:"):
            continue
        names[t.id] = t.name
        is_a[t.id] = [p for p in t.is_a if p.startswith("UBERON:")]
        for x in t.xrefs:
            if x.startswith("FMA:"):
                by_fma[x].append(t.id)
    return by_fma, names, is_a


def laterality_links(
    structures: list[tuple[str, str, str | None]],
    exact: dict[str, str],
    by_fma: dict[str, list[str]],
    uberon_names: dict[str, str],
    uberon_is_a: dict[str, list[str]],
    fma_names: dict[str, str],
    fma_supers: dict[str, set[str]],
) -> list[tuple[str, str, str, str, str, str]]:
    """(fma_id, uberon_id, basis, via_id, via_label, unsided_label) ereditati dalla
    versione senza lato.

    Due strade, entrambe su relazioni dichiarate dalle fonti:
    1. FMA: la struttura ⊑ la sua versione senza lato (stesso nome a meno del lato), che
       ha un xref UBERON esatto.
    2. UBERON: il termine esatto della struttura ha un lato ed è is_a della sua versione
       senza lato. Qui il confronto tra nomi UBERON non basta: UBERON usa a volte un
       termine più largo come xref ("left eye" ↔ FMA "Left eyeball"; "left cardiac
       chamber" ↔ FMA "Left side of heart"). Il termine senza lato è accettato solo se
       si chiama come la struttura a meno del lato, oppure se è l'xref esatto della
       superclasse FMA senza lato.
    Le due strade si sommano (possono arrivare a termini UBERON diversi, entrambi
    legittimi: "adult mammalian kidney" e "kidney"); se coincidono vale la prima."""
    fma_by_uberon: dict[str, set[str]] = defaultdict(set)
    for fma, ubs in by_fma.items():
        for u in ubs:
            fma_by_uberon[u].add(fma)
    out: list[tuple[str, str, str, str, str, str]] = []
    for fma_id, label, _region in structures:
        name = fma_names.get(fma_id) or label
        own = exact.get(fma_id)
        found: set[str] = {own} if own else set()
        generic = laterality.unsided_parent(name, fma_supers.get(fma_id, ()), fma_names)
        # 1) FMA
        if generic:
            hits = sorted(set(by_fma.get(generic, [])))
            if len(hits) == 1 and hits[0] not in found:
                g = fma_names[generic]
                out.append((fma_id, hits[0], "fma_laterality", generic, g, g))
                found.add(hits[0])
        # 2) UBERON
        if own:
            parent = laterality.unsided_parent(
                uberon_names.get(own, ""), uberon_is_a.get(own, []), uberon_names
            )
            if parent is None or parent in found:
                continue
            same_name = laterality.unsided_name(name) == uberon_names[parent].strip().lower()
            same_entity = generic is not None and generic in fma_by_uberon.get(parent, set())
            if same_name or same_entity:
                out.append(
                    (
                        fma_id,
                        parent,
                        "uberon_laterality",
                        own,
                        uberon_names[own],
                        uberon_names[parent],
                    )
                )
    return out


def is_a_links(
    structures: list[tuple[str, str, str | None]],
    exact: dict[str, str],
    lateral: list[tuple[str, str, str, str, str, str]],
    by_fma: dict[str, list[str]],
    clinical: set[str],
    fma_names: dict[str, str],
    fma_supers: dict[str, set[str]],
) -> list[taxonomy.IsALink]:
    """Legami dall'antenato FMA più vicino, solo per le strutture che con il legame
    esatto e quelli con lato non raggiungono alcun contenuto clinico."""
    reached: dict[str, set[str]] = defaultdict(set)
    for fma_id, u in exact.items():
        reached[fma_id].add(u)
    for fma_id, u, *_ in lateral:
        reached[fma_id].add(u)
    count = taxonomy.subclass_counter(fma_supers, cap=config.ISA_MAX_DESCENDANTS)
    out: list[taxonomy.IsALink] = []
    for fma_id, _label, _region in structures:
        if reached[fma_id] & clinical:
            continue
        for link in taxonomy.nearest_described_ancestors(
            fma_id,
            fma_supers,
            fma_names,
            by_fma,
            clinical,
            count,
            config.ISA_MAX_HOPS,
            config.ISA_MAX_DESCENDANTS,
        ):
            if link.uberon_id not in reached[fma_id]:
                out.append(link)
    return out


def is_a_report(
    links: list[taxonomy.IsALink],
    labels: dict[str, str],
    regions: dict[str, str | None],
    uberon_names: dict[str, str],
) -> str:
    lines = [
        "# Legami ereditati dalla classe più generale (`fma_is_a`)",
        "",
        f"Limiti: al più {config.ISA_MAX_HOPS} passi `rdfs:subClassOf`; antenato con al più"
        f" {config.ISA_MAX_DESCENDANTS} sottoclassi FMA. Da leggere: un antenato troppo"
        " generico porta contenuti che non dicono nulla della struttura; se succede,"
        " abbassare i limiti in `pipeline/lib/config.py`.",
        "",
        f"Legami: **{len(links)}**.",
        "",
        "## Antenati usati, per numero di strutture",
        "",
        "| antenato FMA | nome | UBERON | strutture |",
        "|---|---|---|---|",
    ]
    by_anc: dict[tuple[str, str, str], int] = defaultdict(int)
    for x in links:
        by_anc[(x.ancestor_id, x.ancestor_label, x.uberon_id)] += 1
    for (anc, name, u), n in sorted(by_anc.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {anc} | {name} | {u} ({uberon_names.get(u, '?')}) | {n} |")
    lines += [
        "",
        "## Tutti i legami",
        "",
        "| regione | fma_id | struttura | passi | antenato | UBERON |",
        "|---|---|---|---|---|---|",
        *[
            f"| {regions.get(x.fma_id) or '—'} | {x.fma_id} | {labels.get(x.fma_id, '')} |"
            f" {x.hops} | {x.ancestor_label} ({x.ancestor_id}) | {x.uberon_id} |"
            for x in sorted(links, key=lambda x: (regions.get(x.fma_id) or "", x.fma_id))
        ],
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    by_fma, uberon_names, uberon_is_a = uberon_by_fma()

    conn = db.connect(config.DB_PATH)
    with conn:
        db.migrate(conn)  # 04 scrive structure_uberon: deve esistere anche su un db vecchio
        structures = db.structure_ids(conn)
        if not structures:
            sys.exit("structure è vuota: eseguire prima 03_load_ontologies")
        pairs: list[tuple[str | None, str]] = []
        unmapped: list[tuple[object, ...]] = []
        for fma_id, label, _region in structures:
            hits = sorted(set(by_fma.get(fma_id, [])))
            if len(hits) == 1:
                pairs.append((hits[0], fma_id))
                continue
            pairs.append((None, fma_id))
            if hits:
                note = "candidati: " + ", ".join(f"{h} ({uberon_names[h]})" for h in hits)
                unmapped.append(("fma_multi_uberon", fma_id, label, note))
            else:
                unmapped.append(("fma_no_uberon", fma_id, label, None))
        db.set_uberon_ids(conn, pairs)
        db.replace_unmapped(conn, ["fma_no_uberon", "fma_multi_uberon"], unmapped)
        exact = {fma_id: u for u, fma_id in pairs if u}
        fma_names, fma_supers = owl.read_fma_taxonomy(config.FMA_OWL)
        inherited = laterality_links(
            structures, exact, by_fma, uberon_names, uberon_is_a, fma_names, fma_supers
        )
        tissue_roots = taxonomy.classes_by_name(fma_names, config.TISSUE_CLASSES)
        for name in sorted(set(config.TISSUE_CLASSES) - set(tissue_roots)):
            print(f"  ! classe FMA per i tessuti non trovata (o ambigua): {name!r}")
        tagged = {fma: config.TISSUE_CLASSES[name] for name, fma in tissue_roots.items()}
        tissues = [(taxonomy.nearest_tag(f, fma_supers, tagged), f) for f, _, _ in structures]
        db.set_tissues(conn, tissues)
        clinical = db.clinical_uberon_ids(conn)
        is_a = is_a_links(structures, exact, inherited, by_fma, clinical, fma_names, fma_supers)
        db.replace_structure_uberon(
            conn,
            [
                *((f, u, "xref", None, None, None) for f, u in sorted(exact.items())),
                *inherited,
                *(
                    (
                        x.fma_id,
                        x.uberon_id,
                        "fma_is_a",
                        x.ancestor_id,
                        x.ancestor_label,
                        x.ancestor_label,
                    )
                    for x in is_a
                ),
            ],
        )

    all_total = len(structures)
    all_mapped = sum(1 for u, _ in pairs if u)
    counts = db.unmapped_counts(conn)
    config.REPORTS.mkdir(parents=True, exist_ok=True)

    summary = [
        "# Copertura FMA → UBERON per regione",
        "",
        "Una struttura senza `uberon_id` è *muta*: nessun fenotipo HPO e nessuna malattia",
        "la raggiungono direttamente.",
        "",
        "Le colonne *con contenuto clinico* contano le strutture che hanno almeno una malattia",
        "o un segno: per il solo legame esatto; aggiungendo i legami ereditati dalla versione",
        "senza lato (es. *Right humerus* → *Humerus*); aggiungendo infine quelli ereditati",
        "dalla classe più generale (es. *Right fourth rib* → *Rib*, vedi `is_a_links.md`).",
        "",
        "| regione | strutture | con `uberon_id` | % | con nodo mesh |"
        " clinico: esatto | + lato | + classe generale | % finale |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for region in config.REGION_KEYS:
        total, mapped, with_mesh = db.region_coverage(conn, region)
        if total == 0:
            continue
        pct = 100 * mapped / total
        clin_exact, clin_side, clin_all = db.region_clinical_coverage(conn, region)
        summary.append(
            f"| {region} | {total} | {mapped} | {pct:.1f}% | {with_mesh} |"
            f" {clin_exact} | {clin_side} | {clin_all} | {100 * clin_all / total:.1f}% |"
        )
        missing = db.region_unmapped(conn, region)
        lines = [
            f"# Strutture non mappate — regione `{region}`",
            "",
            f"- Strutture nella regione: **{total}** ({with_mesh} con nodo mesh proprio)",
            f"- Con `uberon_id`: **{mapped}** ({pct:.1f}%)",
            f"- Senza `uberon_id`: **{total - mapped}** ({100 - pct:.1f}%)",
            "",
            f"## Strutture senza `uberon_id` ({len(missing)})",
            "",
            "| depth | fma_id | label |",
            "|---|---|---|",
            *[f"| {d} | {f} | {lbl} |" for f, lbl, d in missing],
            "",
        ]
        (config.REPORTS / f"unmapped_{region}.md").write_text("\n".join(lines), encoding="utf-8")
        print(
            f"  {region:<11} {mapped:4}/{total:<4} con uberon_id ({pct:.1f}%);"
            f" con contenuto clinico {clin_exact:4} → {clin_side:4} → {clin_all:4}"
        )

    summary += [
        "",
        f"Su tutto il corpo: {all_mapped}/{all_total} ({100 * all_mapped / all_total:.1f}%).",
        "",
        "## Conteggi `unmapped` per tipo (tutto il database)",
        "",
        "| kind | righe |",
        "|---|---|",
        *[f"| `{k}` | {n} |" for k, n in counts],
        "",
    ]
    (config.REPORTS / "coverage.md").write_text("\n".join(summary), encoding="utf-8")
    labels = {f: lbl for f, lbl, _ in structures}
    regions = {f: r for f, _, r in structures}
    (config.REPORTS / "is_a_links.md").write_text(
        is_a_report(is_a, labels, regions, uberon_names), encoding="utf-8"
    )
    conn.close()

    print(f"  corpo intero: {all_mapped}/{all_total}")
    print(f"  legami ereditati destra/sinistra: {len(inherited)}")
    print(f"  legami ereditati dalla classe più generale: {len(is_a)}")
    by_tissue = Counter(t or "—" for t, _ in tissues)
    print(f"  tessuti (livelli della scena): {dict(sorted(by_tissue.items()))}")
    print(f"OK: report in {config.REPORTS.relative_to(config.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
