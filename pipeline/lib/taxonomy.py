"""Ereditarietà dalla classe più generale: FMA `rdfs:subClassOf` risalito fino al
primo antenato che le fonti cliniche descrivono.

"Right fourth rib" ⊑ "Fourth rib" ⊑ "Rib": le fonti cliniche parlano di costole, non
della quarta costola destra. Poiché la relazione è di sottoclasse (ogni quarta costola
destra È una costola), ciò che le fonti dicono della costola vale anche per lei, in
generale. Si eredita solo se tutte queste condizioni sono vere:

1. la struttura non ha già un legame (esatto o con lato) che porti contenuto clinico:
   l'antenato generico non si somma a contenuti specifici, li sostituisce quando mancano;
2. ogni passo della catena è un `rdfs:subClassOf` dichiarato da FMA (nessuna deduzione);
3. l'antenato ha UN solo termine UBERON che lo cita come xref (come per il legame
   esatto: niente scelta tra candidati);
4. quel termine UBERON porta almeno una malattia o un segno;
5. l'antenato è entro `max_hops` passi e non è troppo generico: ha al più
   `max_descendants` sottoclassi in FMA ("Organ", "Anatomical structure" e simili
   porterebbero contenuti che non dicono nulla della struttura).

Vince il livello più vicino; a pari distanza si tengono tutti gli antenati validi
(ordinati per ID), perché FMA può dichiarare più superclassi.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class IsALink:
    fma_id: str
    uberon_id: str
    ancestor_id: str  # la classe FMA da cui si eredita
    ancestor_label: str
    hops: int  # passi rdfs:subClassOf dalla struttura all'antenato


def subclass_counter(supers: Mapping[str, Iterable[str]], cap: int) -> Callable[[str], int]:
    """Funzione che conta le sottoclassi (dirette e indirette) di una classe FMA,
    fermandosi oltre `cap` (basta sapere che è "troppo generica"). Con cache."""
    subs: dict[str, set[str]] = defaultdict(set)
    for child, parents in supers.items():
        for p in parents:
            subs[p].add(child)
    cache: dict[str, int] = {}

    def count(cls: str) -> int:
        if cls in cache:
            return cache[cls]
        seen: set[str] = set()
        frontier = [cls]
        while frontier and len(seen) <= cap:
            nxt: list[str] = []
            for node in frontier:
                for child in subs.get(node, ()):
                    if child not in seen:
                        seen.add(child)
                        nxt.append(child)
            frontier = nxt
        cache[cls] = len(seen)
        return cache[cls]

    return count


def nearest_described_ancestors(
    fma_id: str,
    supers: Mapping[str, Iterable[str]],
    names: Mapping[str, str],
    by_fma: Mapping[str, list[str]],
    clinical: set[str],
    descendants: Callable[[str], int],
    max_hops: int,
    max_descendants: int,
) -> list[IsALink]:
    """Gli antenati FMA più vicini (stesso numero di passi) che soddisfano 2–5."""
    frontier, seen = [fma_id], {fma_id}
    for hops in range(1, max_hops + 1):
        nxt: list[str] = []
        for node in frontier:
            for parent in sorted(supers.get(node, ())):
                if parent not in seen:
                    seen.add(parent)
                    nxt.append(parent)
        if not nxt:
            return []
        found: list[IsALink] = []
        for anc in sorted(nxt):
            hits = sorted(set(by_fma.get(anc, [])))
            if len(hits) != 1 or hits[0] not in clinical:
                continue
            if descendants(anc) > max_descendants:
                continue
            if any(f.uberon_id == hits[0] for f in found):  # due antenati, stesso termine
                continue
            found.append(IsALink(fma_id, hits[0], anc, names.get(anc, anc), hops))
        if found:
            return found
        # Oltre una classe troppo generica non si sale: sopra è ancora più generico.
        frontier = [n for n in nxt if descendants(n) <= max_descendants]
    return []
