"""04 — Crosswalk FMA ↔ UBERON e report delle strutture non mappate.

Il ponte è l'xref `FMA:nnnn` dichiarato sui termini UBERON. Regole:
- esattamente un termine UBERON cita l'FMA ID  → structure.uberon_id
- nessuno                                      → unmapped('fma_no_uberon')
- più di uno                                   → unmapped('fma_multi_uberon'), nessuna scelta
Nessuna deduzione per analogia o per nome (I5): la copertura va misurata, non nascosta.

Scrive anche data/reports/unmapped_<regione>.md, da leggere a ogni esecuzione.
Idempotente: ricalcola e riscrive tutto.

Uso:  python -m pipeline.04_bridge_fma_uberon
"""

import sys
from collections import defaultdict

from pipeline.lib import config, db, obo


def uberon_by_fma() -> tuple[dict[str, list[str]], dict[str, str]]:
    by_fma: dict[str, list[str]] = defaultdict(list)
    names: dict[str, str] = {}
    for t in obo.iter_terms(config.UBERON_OBO):
        if t.obsolete or not t.id.startswith("UBERON:"):
            continue
        names[t.id] = t.name
        for x in t.xrefs:
            if x.startswith("FMA:"):
                by_fma[x].append(t.id)
    return by_fma, names


def main() -> int:
    region = config.ACTIVE_REGION
    by_fma, uberon_names = uberon_by_fma()

    conn = db.connect(config.DB_PATH)
    with conn:
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

    total, mapped, with_mesh = db.region_coverage(conn, region)
    missing = db.region_unmapped(conn, region)
    all_total = len(structures)
    all_mapped = sum(1 for u, _ in pairs if u)
    pct = 100 * mapped / total if total else 0.0

    lines = [
        f"# Strutture non mappate — regione `{region}`",
        "",
        f"- Strutture nella regione: **{total}** ({with_mesh} con nodo mesh proprio)",
        f"- Con `uberon_id`: **{mapped}** ({pct:.1f}%)",
        f"- Senza `uberon_id`: **{total - mapped}** ({100 - pct:.1f}%)",
        f"- Su tutto il corpo: {all_mapped}/{all_total} ({100 * all_mapped / all_total:.1f}%)",
        "",
        "Una struttura senza `uberon_id` è *muta*: nessun fenotipo HPO e nessuna malattia",
        "la raggiungono direttamente.",
        "",
        "## Conteggi `unmapped` per tipo (tutto il database)",
        "",
        "| kind | righe |",
        "|---|---|",
        *[f"| `{k}` | {n} |" for k, n in db.unmapped_counts(conn)],
        "",
        f"## Strutture della regione senza `uberon_id` ({len(missing)})",
        "",
        "| depth | fma_id | label |",
        "|---|---|---|",
        *[f"| {d} | {f} | {lbl} |" for f, lbl, d in missing],
        "",
    ]
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    report = config.REPORTS / f"unmapped_{region}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    conn.close()

    print(f"  {region}: {mapped}/{total} strutture con uberon_id ({pct:.1f}%)")
    print(f"  corpo intero: {all_mapped}/{all_total}")
    print(f"OK: report in {report.relative_to(config.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
