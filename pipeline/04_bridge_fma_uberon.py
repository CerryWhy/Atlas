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

Scrive un report per regione, data/reports/unmapped_<regione>.md, e un riepilogo
data/reports/coverage.md. Vanno letti a ogni esecuzione.
Idempotente: ricalcola e riscrive tutto.

Uso:  python -m pipeline.04_bridge_fma_uberon
"""

import sys
from collections import defaultdict

from pipeline.lib import config, db, laterality, obo, owl


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
    fma_names, fma_supers = owl.read_fma_taxonomy(config.FMA_OWL)
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
        inherited = laterality_links(structures, exact, by_fma, uberon_names, uberon_is_a)
        db.replace_structure_uberon(
            conn,
            [*((f, u, "xref", None, None, None) for f, u in sorted(exact.items())), *inherited],
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
        "La colonna *con contenuto clinico* conta le strutture che hanno almeno una malattia",
        "o un segno: prima per il solo legame esatto, poi includendo i legami ereditati dalla",
        "versione senza lato (es. *Right humerus* → *Humerus*).",
        "",
        "| regione | strutture | con `uberon_id` | % | con nodo mesh |"
        " con contenuto clinico: esatto → con lato ereditato |",
        "|---|---|---|---|---|---|",
    ]
    for region in config.REGION_KEYS:
        total, mapped, with_mesh = db.region_coverage(conn, region)
        if total == 0:
            continue
        pct = 100 * mapped / total
        clin_exact, clin_all = db.region_clinical_coverage(conn, region)
        summary.append(
            f"| {region} | {total} | {mapped} | {pct:.1f}% | {with_mesh} |"
            f" {clin_exact} → {clin_all} |"
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
            f" con contenuto clinico {clin_exact:4} → {clin_all:4}"
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
    conn.close()

    print(f"  corpo intero: {all_mapped}/{all_total}")
    print(f"  legami ereditati destra/sinistra: {len(inherited)}")
    print(f"OK: report in {config.REPORTS.relative_to(config.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
