"""Ereditarietà destra/sinistra: dalla struttura con lato alla stessa senza lato.

Le fonti cliniche (MONDO, HPO, Disease Ontology) parlano di "omero" o "rene", quasi mai
di "omero destro". Una struttura con lato eredita i legami clinici della sua versione
senza lato solo se ENTRAMBE queste condizioni sono vere:

1. la fonte dichiara la relazione di sottoclasse (FMA `rdfs:subClassOf`, UBERON `is_a`):
   la relazione non è dedotta, è letta dal file;
2. il nome della struttura è esattamente "Right <X>" / "Left <X>" e il nome della
   superclasse è esattamente "<X>".

La seconda condizione esclude le strutture che hanno "left/right" nel nome senza esserne
la versione con lato (es. "Left gastric artery" è un'arteria a sé, non la gastrica di
sinistra; "Right side of heart" non è un "side of heart" con lato).
"""

import re
from collections.abc import Iterable, Mapping

_SIDED = re.compile(r"^(right|left)\s+(\S.*)$", re.IGNORECASE)


def unsided_name(name: str) -> str | None:
    """'Right humerus' → 'humerus'; None se il nome non comincia con un lato."""
    m = _SIDED.match(name.strip())
    return m.group(2).strip().lower() if m else None


def unsided_parent(name: str, parents: Iterable[str], names: Mapping[str, str]) -> str | None:
    """La superclasse dichiarata che è la stessa struttura senza lato, se è una sola."""
    want = unsided_name(name)
    if want is None:
        return None
    hits = sorted({p for p in parents if names.get(p, "").strip().lower() == want})
    return hits[0] if len(hits) == 1 else None
