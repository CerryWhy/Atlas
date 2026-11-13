"""Documento → malattia (MONDO) e documento → struttura (FMA), dai riferimenti che la
fonte dichiara (document_ref). Nessun legame per somiglianza (I5): solo codici
dichiarati, equivalenze esatte di MONDO/UBERON e uguaglianza esatta di nomi.

Malattie (basis):
- 'source_mondo'        la fonte cita il MONDO ID (Orphanet, mapping "E" esatto)
- 'mondo_xref_orphanet' l'ORPHAcode è xref equivalente di UN solo termine MONDO
- 'mondo_xref_mesh'     il descrittore MeSH è xref equivalente di UN solo termine MONDO
- 'title_exact'         (StatPearls) il titolo è, a meno di maiuscole, il nome o un
                        sinonimo EXACT di UN solo termine MONDO

Strutture (basis, relevance):
- 'anatomy_title' 1.0   capitolo di anatomia: l'oggetto del titolo è il nome FMA della
                        struttura, o il nome/sinonimo EXACT di UN solo termine UBERON
                        legato alla struttura (anche con lato: "Calcaneus" → destro/sinistro)
- 'mesh_anatomy'  0.8   il descrittore MeSH è xref di UN solo termine UBERON
- 'disease_site'  0.5   il documento parla di una malattia con sede nella struttura
- 'disease_site_part' 0.4  …con sede in una PARTE della struttura (UBERON part_of
                        dichiarato, al più MAX_PART_OF_HOPS passi): una malattia del
                        lobulo epatico riguarda il fegato. Non si arriva alle strutture
                        "larghe" (apparati, regioni: Vocab.broad), che non direbbero nulla
- 'container'     0.3   ultima risorsa, per le strutture rimaste senza documenti: i
                        documenti diretti della struttura che le contiene, la più vicina
                        (albero part_of della scena, o part_of/is_a di UBERON), al più
                        MAX_CONTAINER_HOPS passi, mai un apparato intero (Vocab.broad)
                        né una categoria UBERON (Vocab.uberon_generic: "artery");
                        al più MAX_CONTAINER_DOCS. "Lobo destro del fegato" → "fegato"
Per ogni coppia documento–struttura vale il legame più forte.

I titoli di anatomia di StatPearls premettono spesso la regione ("Foot Talus",
"Thigh Gracilis Muscle") o usano il plurale ("Subclavian Arteries"): oltre al nome
così com'è si provano, in quest'ordine, poche varianti a regola fissa (singolare;
senza la prima parola SE è una regione di REGION_PREFIXES; entrambe), sempre per
uguaglianza esatta, e `via` registra la forma che ha trovato la corrispondenza.
Togliere una parola qualsiasi non è sicuro: "Lumbosacral Trunk" diventerebbe "trunk".
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

RELEVANCE = {
    "anatomy_title": 1.0,
    "mesh_anatomy": 0.8,
    "disease_site": 0.5,
    "disease_site_part": 0.4,
    "container": 0.3,
}
# Legami "diretti": dicono qualcosa della struttura stessa e si possono ereditare.
DIRECT = ("anatomy_title", "mesh_anatomy", "disease_site")
MAX_CONTAINER_HOPS = 2
MAX_CONTAINER_DOCS = 25
# Un termine UBERON con più sottoclassi (is_a) di così è una categoria, non un
# contenitore: "artery" (440), "vein" (360), "vertebra" (50) direbbero poco della
# struttura. Misurato su UBERON 2026: i contenitori utili ne hanno ≤ 16 ("bile duct"),
# le categorie ≥ 50; la soglia sta nel vuoto tra i due gruppi.
MAX_CONTAINER_SUBCLASSES = 30
MAX_PART_OF_HOPS = 2


def singular(name: str) -> str:
    """Singolare dell'ultima parola, per le sole regole regolari dell'inglese."""
    head, _, last = name.rpartition(" ")
    if last.endswith("ies") and len(last) > 4:
        last = last[:-3] + "y"
    elif last.endswith(("ches", "shes", "sses", "xes")):
        last = last[:-2]
    elif last.endswith("s") and not last.endswith(("ss", "us", "is")):
        last = last[:-1]
    return f"{head} {last}".strip()


# Regioni che StatPearls premette all'oggetto nei titoli della serie di anatomia.
REGION_PREFIXES = frozenset(
    "abdomen ankle arm back brain calf chest ear elbow eye face finger foot forearm hand "
    "head heart hip knee leg neck pelvis shoulder skull thigh thorax toe wrist".split()
)


def name_variants(name: str) -> list[str]:
    """Il nome, il singolare, senza la regione iniziale, entrambe (senza ripetizioni)."""
    base = norm(name)
    out = [base, singular(base)]
    words = base.split(" ")
    if len(words) > 1 and words[0] in REGION_PREFIXES:
        rest = " ".join(words[1:])
        out += [rest, singular(rest)]
    return list(dict.fromkeys(out))


def norm(name: str) -> str:
    """Confronto di nomi: minuscole, spazi compattati, senza punto finale."""
    return re.sub(r"\s+", " ", name.strip().lower()).rstrip(".")


def unique_index(pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    """chiave → valore, tenendo solo le chiavi con UN solo valore."""
    seen: dict[str, set[str]] = defaultdict(set)
    for key, value in pairs:
        seen[key].add(value)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


@dataclass
class Vocab:
    """Ciò che serve a risolvere i riferimenti, letto dai file e da atlas.db."""

    mondo_by_xref: Mapping[str, str]  # 'MESH:D006442' | 'Orphanet:166024' → MONDO (univoci)
    mondo_by_name: Mapping[str, str]  # nome normalizzato → MONDO (univoci)
    diseases: set[str]  # MONDO presenti in atlas.db
    uberon_by_mesh: Mapping[str, str]  # 'MESH:D008099' → UBERON (univoci)
    uberon_by_name: Mapping[str, str]  # nome normalizzato → UBERON (univoci)
    fma_by_name: Mapping[str, str]  # label_en normalizzato → FMA (univoci)
    structures_by_uberon: Mapping[str, set[str]]  # UBERON → FMA (structure_uberon)
    disease_sites: Mapping[str, set[str]]  # MONDO → UBERON (disease_structure)
    uberon_part_of: Mapping[str, set[str]]  # UBERON → i "tutto" dichiarati (part_of)
    broad: frozenset[str] = frozenset()  # FMA troppo larghe per la risalita part_of
    structure_parent: Mapping[str, str] = field(default_factory=dict)  # FMA → FMA genitore
    # UBERON → superclassi (is_a): solo per la risalita 'container', non per le sedi
    uberon_is_a: Mapping[str, set[str]] = field(default_factory=dict)
    # UBERON con più di MAX_CONTAINER_SUBCLASSES sottoclassi: né contenitore né passaggio
    uberon_generic: frozenset[str] = frozenset()
    labels: Mapping[str, str] = field(default_factory=dict)  # FMA/UBERON → nome


DiseaseLink = tuple[str, str, str, str]  # doc_id, mondo_id, basis, via
StructureLink = tuple[str, str, float, str, str]  # doc_id, fma_id, relevance, basis, via


def link(
    refs: Iterable[tuple[str, str, str]],
    titles: Mapping[str, tuple[str, str]],  # doc_id → (source, title)
    v: Vocab,
) -> tuple[list[DiseaseLink], list[StructureLink]]:
    refs = list(refs)
    diseases: dict[tuple[str, str], DiseaseLink] = {}
    structures: dict[tuple[str, str], StructureLink] = {}

    def add_disease(doc: str, mondo: str, basis: str, via: str) -> None:
        if mondo in v.diseases:
            diseases.setdefault((doc, mondo), (doc, mondo, basis, via))

    # documenti per termine UBERON, anche quando nessuna struttura in scena lo porta:
    # servono alla risalita 'container'
    by_uberon: dict[str, set[str]] = defaultdict(set)

    def add_structure(doc: str, fma: str, basis: str, via: str) -> None:
        rel = RELEVANCE[basis]
        old = structures.get((doc, fma))
        if old is None or old[2] < rel:
            structures[(doc, fma)] = (doc, fma, rel, basis, via)

    for doc, scheme, code in refs:
        if scheme == "MONDO":
            add_disease(doc, code, "source_mondo", code)
        elif scheme in ("Orphanet", "MESH"):
            key = f"{scheme}:{code}"
            basis = "mondo_xref_orphanet" if scheme == "Orphanet" else "mondo_xref_mesh"
            if (mondo := v.mondo_by_xref.get(key)) is not None:
                add_disease(doc, mondo, basis, key)
            if scheme == "MESH" and (uberon := v.uberon_by_mesh.get(key)) is not None:
                by_uberon[uberon].add(doc)
                for fma in v.structures_by_uberon.get(uberon, ()):
                    add_structure(doc, fma, "mesh_anatomy", key)
        elif scheme == "anatomy":
            for name in name_variants(code):
                hits: set[str] = set()
                if (named := v.fma_by_name.get(name)) is not None:
                    hits = {named}
                elif (uberon := v.uberon_by_name.get(name)) is not None:
                    hits = set(v.structures_by_uberon.get(uberon, ()))
                    by_uberon[uberon].add(doc)
                for fma in hits:
                    add_structure(doc, fma, "anatomy_title", name)
                if hits:
                    break

    # StatPearls: i capitoli che non sono di anatomia e si chiamano come una malattia
    anatomy_docs = {doc for doc, scheme, _ in refs if scheme == "anatomy"}
    for doc, (source, title) in titles.items():
        if source != "statpearls" or doc in anatomy_docs:
            continue
        if (mondo := v.mondo_by_name.get(norm(title))) is not None:
            add_disease(doc, mondo, "title_exact", title)

    # dalla malattia alla sua sede (o, se la sede non è in scena, al "tutto" più vicino)
    for doc, mondo, _basis, _via in list(diseases.values()):
        for uberon in v.disease_sites.get(mondo, ()):
            by_uberon[uberon].add(doc)
            for fma, hops in _site_structures(uberon, v):
                add_structure(doc, fma, "disease_site" if hops == 0 else "disease_site_part", mondo)

    # ultima risorsa: dalla struttura che contiene quella rimasta senza documenti
    direct: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for doc, fma, rel, basis, _via in structures.values():
        if basis in DIRECT:
            direct[fma].append((rel, doc))
    uberons_of: dict[str, set[str]] = defaultdict(set)
    for u, fmas in v.structures_by_uberon.items():
        for f in fmas:
            uberons_of[f].add(u)
    covered = {fma for _doc, fma in structures}
    for fma in sorted(set(v.structure_parent) | set(uberons_of)):
        if fma in covered:
            continue
        whole, docs = _container_docs(fma, v, direct, by_uberon, uberons_of)
        for doc in docs:
            add_structure(doc, fma, "container", whole)

    return sorted(diseases.values()), sorted(structures.values())


def _container_docs(
    fma: str,
    v: Vocab,
    direct: Mapping[str, list[tuple[float, str]]],
    by_uberon: Mapping[str, set[str]],
    uberons_of: Mapping[str, set[str]],
) -> tuple[str, list[str]]:
    """("nome (ID)" del contenitore più vicino con documenti diretti, i suoi documenti).
    Risale insieme l'albero della scena (FMA) e part_of di UBERON, un passo alla volta;
    a parità di distanza vince l'ID più basso. Non attraversa le strutture larghe."""
    frontier: list[str] = [fma, *sorted(uberons_of.get(fma, ()))]
    seen = set(frontier)
    for _hop in range(MAX_CONTAINER_HOPS):
        nxt: list[str] = []
        for node in frontier:
            if node.startswith("UBERON:"):
                ups = sorted(v.uberon_part_of.get(node, set()) | v.uberon_is_a.get(node, set()))
            else:
                parent = v.structure_parent.get(node)
                ups = [parent] if parent and parent not in v.broad else []
                if parent and parent not in v.broad:
                    ups += sorted(uberons_of.get(parent, ()))
            for up in ups:
                if up in v.uberon_generic:
                    continue
                if up not in seen:
                    seen.add(up)
                    nxt.append(up)
        hits = []
        for node in sorted(nxt):
            if node.startswith("UBERON:"):
                docs = sorted(by_uberon.get(node, ()))
            else:
                docs = [d for _r, d in sorted(direct.get(node, ()), key=lambda x: (-x[0], x[1]))]
            if docs:
                hits.append((node, docs))
        if hits:
            # preferisci una struttura in scena (FMA) a un termine UBERON
            node, docs = min(hits, key=lambda h: (h[0].startswith("UBERON:"), h[0]))
            label = v.labels.get(node, node)
            return f"{label} ({node})", docs[:MAX_CONTAINER_DOCS]
        frontier = nxt
    return "", []


def _site_structures(uberon: str, v: Vocab) -> list[tuple[str, int]]:
    """Strutture della sede, o dei suoi "tutto" più vicini risalendo part_of."""
    frontier, seen = [uberon], {uberon}
    for hops in range(MAX_PART_OF_HOPS + 1):
        found = [
            (f, hops)
            for u in frontier
            for f in v.structures_by_uberon.get(u, ())
            if hops == 0 or f not in v.broad
        ]
        if found:
            return found
        frontier = [w for u in frontier for w in v.uberon_part_of.get(u, ()) if w not in seen]
        seen.update(frontier)
    return []
