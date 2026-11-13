"""Nomi italiani da Wikidata, agganciati all'ID FMA (proprietà P1402, "FMA ID").

FMA ha pochissimi equivalenti italiani; Wikidata (dati CC0) ne ha molti di più e cita
l'ID FMA sulle voci anatomiche. Il file in data/raw/ è il risultato JSON di una query
SPARQL (config.WIKIDATA_QUERY), scaricato da 01 come le altre fonti.

Si accetta un nome solo se il legame è uno a uno e non ambiguo (I5):
- l'ID FMA compare su UNA sola voce Wikidata;
- quella voce porta UN solo ID FMA (una voce con più ID FMA è di solito un concetto
  più largo o una fusione: il suo nome non è quello di ciascuna struttura);
- la voce ha esattamente un'etichetta italiana.
Le altre righe finiscono nel conteggio degli scarti, mai in `label_it`.
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ENTITY_PREFIX = "http://www.wikidata.org/entity/"


@dataclass(frozen=True)
class ItalianLabel:
    fma_id: str
    label: str
    qid: str  # 'Q9368'


@dataclass(frozen=True)
class LabelStats:
    accepted: int
    fma_on_many_items: int
    item_with_many_fma: int


def _value(binding: dict[str, dict[str, str]], key: str) -> str | None:
    cell = binding.get(key)
    return cell.get("value") if cell else None


def parse_sparql(path: Path) -> tuple[dict[str, ItalianLabel], LabelStats]:
    """FMA ID → nome italiano, dal JSON SPARQL con variabili ?item ?fma ?label."""
    data = json.loads(path.read_text(encoding="utf-8"))
    items_by_fma: dict[str, set[str]] = defaultdict(set)
    fma_by_item: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, set[str]] = defaultdict(set)
    for b in data["results"]["bindings"]:
        item, fma, label = _value(b, "item"), _value(b, "fma"), _value(b, "label")
        if not item or not item.startswith(ENTITY_PREFIX) or not fma or not fma.isdigit():
            continue
        qid = item[len(ENTITY_PREFIX) :]
        fma_id = f"FMA:{fma}"
        items_by_fma[fma_id].add(qid)
        fma_by_item[qid].add(fma_id)
        if label and label.strip():
            labels[qid].add(label.strip())

    out: dict[str, ItalianLabel] = {}
    many_items = many_fma = 0
    for fma_id, qids in items_by_fma.items():
        if len(qids) != 1:
            many_items += 1
            continue
        (qid,) = qids
        if len(fma_by_item[qid]) != 1:
            many_fma += 1
            continue
        if len(labels[qid]) == 1:
            (label,) = labels[qid]
            out[fma_id] = ItalianLabel(fma_id, label, qid)
    return out, LabelStats(len(out), many_items, many_fma)
