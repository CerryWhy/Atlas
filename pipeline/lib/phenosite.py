"""Fenotipo HPO → strutture in scena, per /locate (Fase 5).

Due passi, entrambi su relazioni dichiarate (I5):

1. Sede del fenotipo. Se la definizione logica di HPO la dichiara (inheres_in,
   inheres_in_part_of → UBERON) vale quella ('logical'). Molti sintomi comuni non ne
   hanno una ("Abdominal pain", "Knee pain"): allora si eredita dall'antenato is_a più
   vicino che la dichiara ('inherited'). È la semantica OWL della sottoclasse: se ogni
   "Back pain" è un'"Abnormality of the vertebral column", e questa ha sede nella
   colonna, anche il mal di schiena ce l'ha. Al più MAX_HPO_HOPS passi.

2. Dalla sede alle strutture: le strutture legate a quel termine UBERON
   (structure_uberon); se nessuna lo è, il "tutto" più vicino risalendo part_of di
   UBERON (al più MAX_SITE_HOPS passi, mai fino a una struttura larga): la gengiva non è
   in scena, la bocca sì.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

MAX_HPO_HOPS = 4
MAX_SITE_HOPS = 2
SITE_RELATIONS = frozenset({"inheres_in", "inheres_in_part_of"})


@dataclass(frozen=True)
class Locus:
    hpo_id: str
    fma_id: str
    uberon_id: str  # la sede dichiarata (prima della risalita part_of)
    basis: str  # 'logical' | 'inherited'
    via_hpo: str  # il fenotipo che dichiara la sede (sé stesso se 'logical')
    hops: int  # passi is_a in HPO + passi part_of in UBERON


def own_sites(relations: Mapping[str, Iterable[tuple[str, str]]]) -> dict[str, set[str]]:
    """HPO → sedi UBERON dalle sole definizioni logiche."""
    out: dict[str, set[str]] = defaultdict(set)
    for hpo, rels in relations.items():
        for rel, target in rels:
            if rel in SITE_RELATIONS and target.startswith("UBERON:"):
                out[hpo].add(target)
    return out


def phenotype_sites(
    hpo_id: str, is_a: Mapping[str, Iterable[str]], sites: Mapping[str, set[str]]
) -> list[tuple[str, str, int]]:
    """(sede UBERON, fenotipo che la dichiara, passi) dell'antenato più vicino che ne ha.
    A pari distanza si tengono tutti (un fenotipo può avere più superclassi)."""
    frontier, seen = [hpo_id], {hpo_id}
    for hops in range(MAX_HPO_HOPS + 1):
        found = sorted((u, h, hops) for h in frontier for u in sites.get(h, ()))
        if found:
            return found
        frontier = sorted({p for h in frontier for p in is_a.get(h, ()) if p not in seen})
        seen.update(frontier)
        if not frontier:
            break
    return []


def site_structures(
    uberon: str,
    structures_by_uberon: Mapping[str, set[str]],
    part_of: Mapping[str, set[str]],
    broad: frozenset[str],
) -> list[tuple[str, int]]:
    """(struttura, passi part_of) per la sede, o per il suo "tutto" più vicino in scena."""
    frontier, seen = [uberon], {uberon}
    for hops in range(MAX_SITE_HOPS + 1):
        found = sorted(
            (f, hops)
            for u in frontier
            for f in structures_by_uberon.get(u, ())
            if hops == 0 or f not in broad
        )
        if found:
            return found
        frontier = sorted({w for u in frontier for w in part_of.get(u, ()) if w not in seen})
        seen.update(frontier)
    return []


def loci(
    hpo_ids: Iterable[str],
    is_a: Mapping[str, Iterable[str]],
    sites: Mapping[str, set[str]],
    structures_by_uberon: Mapping[str, set[str]],
    part_of: Mapping[str, set[str]],
    broad: frozenset[str],
) -> list[Locus]:
    out: dict[tuple[str, str], Locus] = {}
    for hpo in sorted(hpo_ids):
        for uberon, via, hpo_hops in phenotype_sites(hpo, is_a, sites):
            for fma, site_hops in site_structures(uberon, structures_by_uberon, part_of, broad):
                locus = Locus(
                    hpo,
                    fma,
                    uberon,
                    "logical" if via == hpo else "inherited",
                    via,
                    hpo_hops + site_hops,
                )
                old = out.get((hpo, fma))
                if old is None or (locus.hops, locus.uberon_id) < (old.hops, old.uberon_id):
                    out[(hpo, fma)] = locus
    return sorted(out.values(), key=lambda x: (x.hpo_id, x.fma_id))
