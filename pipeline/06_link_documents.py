"""06 — Documenti → malattie (MONDO) e strutture (FMA).

Risolve i riferimenti dichiarati dalle fonti (document_ref, scritti da 05) con le
equivalenze esatte di MONDO e UBERON e i legami struttura ↔ UBERON di 04. Le regole
sono in pipeline/lib/doclinks.py; ogni legame registra `basis` e `via` per essere
citato (I2). Nessun legame per somiglianza di testo (I5).

Scrive data/reports/documents.md: quanti documenti sono collegati, per fonte e per
tipo di legame, e quali strutture con `uberon_id` restano senza documenti (criterio
di accettazione della Fase 3, regione addome). Va letto a ogni esecuzione.
Idempotente: ricalcola tutti i legami.

Uso:  python -m pipeline.06_link_documents
"""

import sys
from collections import Counter

from pipeline.lib import config, db, doclinks, obo, taxonomy

ACCEPTANCE_REGION = "abdomen"
# Come per il fuoco di un clic (api/queries.py): sotto questa profondità c'è un apparato
# o una regione intera, troppo larghi come arrivo della risalita part_of.
MIN_TARGET_DEPTH = 3


def mondo_vocab() -> tuple[dict[str, str], dict[str, str]]:
    by_xref: list[tuple[str, str]] = []
    by_name: list[tuple[str, str]] = []
    for t in obo.iter_terms(config.MONDO_OBO):
        if t.obsolete or not t.id.startswith("MONDO:"):
            continue
        by_xref += [(x, t.id) for x in t.equivalent_xrefs if x.startswith(("MESH:", "Orphanet:"))]
        by_name += [(doclinks.norm(n), t.id) for n in (t.name, *t.exact_synonyms) if n]
    return doclinks.unique_index(by_xref), doclinks.unique_index(by_name)


def uberon_vocab() -> tuple[
    dict[str, str], dict[str, str], dict[str, set[str]], dict[str, str], dict[str, set[str]]
]:
    by_mesh: list[tuple[str, str]] = []
    by_name: list[tuple[str, str]] = []
    part_of: dict[str, set[str]] = {}
    names: dict[str, str] = {}
    is_a: dict[str, set[str]] = {}
    for t in obo.iter_terms(config.UBERON_OBO):
        if t.obsolete or not t.id.startswith("UBERON:"):
            continue
        names[t.id] = t.name
        by_mesh += [(x, t.id) for x in t.xrefs if x.startswith("MESH:")]
        by_name += [(doclinks.norm(n), t.id) for n in (t.name, *t.exact_synonyms) if n]
        wholes = {w for rel, w in t.relations if rel == "part_of" and w.startswith("UBERON:")}
        if wholes:
            part_of[t.id] = wholes
        supers = {p for p in t.is_a if p.startswith("UBERON:")}
        if supers:
            is_a[t.id] = supers
    return doclinks.unique_index(by_mesh), doclinks.unique_index(by_name), part_of, names, is_a


# Le sottoclassi di questo termine UBERON (cercato per nome, I5) sono sistemi
# ("digestive system", "renal system"): mai contenitori, come gli apparati in scena.
SYSTEM_ROOT_NAME = "anatomical system"


def generic_terms(is_a: dict[str, set[str]], names: dict[str, str]) -> frozenset[str]:
    """Termini UBERON che non fanno da contenitore (doclinks): le categorie con più di
    MAX_CONTAINER_SUBCLASSES sottoclassi e i sistemi anatomici."""
    cap = doclinks.MAX_CONTAINER_SUBCLASSES
    count = taxonomy.subclass_counter(is_a, cap=cap)
    terms = is_a.keys() | {p for ps in is_a.values() for p in ps}
    generic = {u for u in terms if count(u) > cap}
    roots = [u for u, n in names.items() if n == SYSTEM_ROOT_NAME]
    if len(roots) != 1:
        print(
            f"  ! termine UBERON {SYSTEM_ROOT_NAME!r} non trovato (o ambiguo): sistemi non bloccati"
        )
        return frozenset(generic)
    subs: dict[str, set[str]] = {}
    for child, parents in is_a.items():
        for p in parents:
            subs.setdefault(p, set()).add(child)
    frontier, systems = [roots[0]], {roots[0]}
    while frontier:
        frontier = [c for u in frontier for c in subs.get(u, ()) if c not in systems]
        systems.update(frontier)
    return frozenset(generic | systems)


def main() -> int:
    conn = db.connect(config.DB_PATH)
    with conn:
        db.migrate(conn)
        refs = db.document_refs(conn)
        if not refs:
            sys.exit("document_ref è vuota: eseguire prima 05_ingest_documents")
        diseases, names, uberon_links, sites = db.link_vocab_rows(conn)
        mondo_xref, mondo_name = mondo_vocab()
        uberon_mesh, uberon_name, uberon_part_of, uberon_labels, uberon_is_a = uberon_vocab()
        structures_by_uberon: dict[str, set[str]] = {}
        for u, f in uberon_links:
            structures_by_uberon.setdefault(u, set()).add(f)
        disease_sites: dict[str, set[str]] = {}
        for m, u in sites:
            disease_sites.setdefault(m, set()).add(u)
        vocab = doclinks.Vocab(
            mondo_by_xref=mondo_xref,
            mondo_by_name=mondo_name,
            diseases=diseases,
            uberon_by_mesh=uberon_mesh,
            uberon_by_name=uberon_name,
            fma_by_name=doclinks.unique_index((doclinks.norm(n), f) for n, f in names),
            structures_by_uberon=structures_by_uberon,
            disease_sites=disease_sites,
            uberon_part_of=uberon_part_of,
            broad=db.broad_structures(conn, MIN_TARGET_DEPTH),
            structure_parent=db.structure_parents(conn),
            uberon_is_a=uberon_is_a,
            uberon_generic=generic_terms(uberon_is_a, uberon_labels),
            labels={**uberon_labels, **{f: n for n, f in names}},
        )
        titles = db.document_titles(conn)
        to_disease, to_structure = doclinks.link(refs, titles, vocab)
        db.replace_document_links(conn, to_disease, to_structure)
        missing = db.abdominal_structures_without_documents(conn, ACCEPTANCE_REGION)
        with_uberon = conn.execute(
            "SELECT COUNT(*) FROM structure WHERE region = ? AND uberon_id IS NOT NULL",
            (ACCEPTANCE_REGION,),
        ).fetchone()[0]
    conn.close()

    by_source = Counter(src for src, _ in titles.values())
    linked = {d for d, *_ in to_disease} | {d for d, *_ in to_structure}
    linked_by_source = Counter(titles[d][0] for d in linked)
    lines = [
        "# Documenti collegati",
        "",
        "| fonte | documenti | collegati a malattie o strutture | % |",
        "|---|---|---|---|",
        *[
            f"| {s} | {n} | {linked_by_source[s]} | {100 * linked_by_source[s] / n:.1f}% |"
            for s, n in sorted(by_source.items())
        ],
        "",
        "## Legami per tipo",
        "",
        "| tipo | legami documento → malattia |",
        "|---|---|",
        *[f"| `{b}` | {n} |" for b, n in sorted(Counter(x[2] for x in to_disease).items())],
        "",
        "| tipo | legami documento → struttura | strutture raggiunte |",
        "|---|---|---|",
        *[
            f"| `{b}` | {n} | {len({x[1] for x in to_structure if x[3] == b})} |"
            for b, n in sorted(Counter(x[3] for x in to_structure).items())
        ],
        "",
        f"## Accettazione Fase 3 — regione `{ACCEPTANCE_REGION}`",
        "",
        f"Strutture con `uberon_id`: **{with_uberon}**; senza alcun documento:"
        f" **{len(missing)}**. Il criterio chiede zero.",
        "",
        "| fma_id | struttura |",
        "|---|---|",
        *[f"| {f} | {lbl} |" for f, lbl in missing],
        "",
    ]
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    (config.REPORTS / "documents.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  documento → malattia: {len(to_disease)}; documento → struttura: {len(to_structure)}")
    print(f"  documenti collegati: {dict(linked_by_source)} su {dict(by_source)}")
    print(f"  {ACCEPTANCE_REGION}: {len(missing)} strutture con uberon_id senza documenti")
    print("OK: report in data/reports/documents.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
