"""Lettura in streaming di OWL/RDF-XML: FMA (208 MB) e Disease Ontology.

Non è un parser OWL generale: estrae solo ciò che la pipeline usa, con iterparse
per non caricare il file in memoria.
"""

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
RDFS = "{http://www.w3.org/2000/01/rdf-schema#}"
OWL = "{http://www.w3.org/2002/07/owl#}"
FMA = "{http://purl.org/sig/ont/fma/}"

FMA_IRI = "http://purl.org/sig/ont/fma/fma"
OBO_IRI = "http://purl.obolibrary.org/obo/"

FMA_PART_OF = {
    "http://purl.org/sig/ont/fma/part_of",
    "http://purl.org/sig/ont/fma/regional_part_of",
    "http://purl.org/sig/ont/fma/constitutional_part_of",
}
FMA_NON_ENGLISH = "http://purl.org/sig/ont/fma/non-English_equivalent"


def _top_level(path: Path) -> Iterator[ET.Element]:
    """Elementi figli diretti di rdf:RDF, liberati dopo l'uso."""
    depth = 0
    for event, elem in ET.iterparse(path, events=("start", "end")):
        if event == "start":
            depth += 1
            continue
        depth -= 1
        if depth == 1:
            yield elem
            elem.clear()


def _fma_curie(iri: str | None) -> str | None:
    if iri and iri.startswith(FMA_IRI) and iri[len(FMA_IRI) :].isdigit():
        return "FMA:" + iri[len(FMA_IRI) :]
    return None


@dataclass
class FmaClass:
    fma_id: str
    label: str | None = None
    preferred_name: str | None = None
    part_of: set[str] = field(default_factory=set)  # FMA ID dei "tutto" dichiarati
    # equivalenti non inglesi con lingua dichiarata: lingua → nomi
    equivalents: dict[str, list[str]] = field(default_factory=dict)


def read_fma(path: Path, wanted: set[str]) -> tuple[dict[str, FmaClass], str, dict[str, set[str]]]:
    """Classi FMA richieste, versione dell'ontologia e grafo part_of di TUTTA FMA
    (parte → tutti), per poter risalire oltre le classi richieste."""
    out: dict[str, FmaClass] = {}
    graph: dict[str, set[str]] = {}
    version = ""
    for elem in _top_level(path):
        if elem.tag == OWL + "Ontology":
            version = elem.findtext(OWL + "versionInfo") or ""
        elif elem.tag == OWL + "Class":
            fma_id = _fma_curie(elem.get(RDF + "about"))
            if fma_id is None:
                continue
            wholes: set[str] = set()
            for restr in elem.iterfind(f"{RDFS}subClassOf/{OWL}Restriction"):
                prop = restr.find(OWL + "onProperty")
                target = restr.find(OWL + "someValuesFrom")
                if prop is None or target is None:
                    continue
                whole = _fma_curie(target.get(RDF + "resource"))
                if prop.get(RDF + "resource") in FMA_PART_OF and whole:
                    wholes.add(whole)
            if wholes:
                graph[fma_id] = wholes
            if fma_id not in wanted:
                continue
            cls = out.setdefault(fma_id, FmaClass(fma_id))
            cls.label = elem.findtext(RDFS + "label")
            cls.preferred_name = elem.findtext(FMA + "preferred_name")
            cls.part_of = set(wholes)
        elif elem.tag == OWL + "Axiom":
            prop = elem.find(OWL + "annotatedProperty")
            if prop is None or prop.get(RDF + "resource") != FMA_NON_ENGLISH:
                continue
            src = elem.find(OWL + "annotatedSource")
            fma_id = _fma_curie(src.get(RDF + "resource") if src is not None else None)
            language = elem.findtext(FMA + "language")
            name = elem.findtext(OWL + "annotatedTarget")
            if fma_id in wanted and fma_id and language and name:
                cls = out.setdefault(fma_id, FmaClass(fma_id))
                cls.equivalents.setdefault(language, []).append(name)
    if not version:
        raise LookupError(f"{path.name} senza owl:versionInfo")
    return out, version, graph


def nearest_whole(start: str, graph: dict[str, set[str]], targets: set[str]) -> str | None:
    """Il "tutto" più vicino tra `targets`, risalendo part_of in ampiezza (BFS).
    A parità di distanza vince l'ID più basso, per avere un risultato stabile."""
    frontier, seen = [start], {start}
    while frontier:
        hits = sorted(t for t in frontier if t in targets)
        if hits:
            return hits[0]
        nxt: list[str] = []
        for node in frontier:
            for whole in sorted(graph.get(node, ())):
                if whole not in seen:
                    seen.add(whole)
                    nxt.append(whole)
        frontier = nxt
    return None


def read_restrictions(path: Path, prop_iri: str, subject_prefix: str) -> list[tuple[str, str]]:
    """(soggetto, oggetto) CURIE per ogni `soggetto ⊑ ∃prop.oggetto` del file.

    Considera le restrizioni ovunque dentro la classe (anche dentro una
    intersezione in equivalentClass: l'assioma di sede ne è comunque implicato).
    """
    out: list[tuple[str, str]] = []
    for elem in _top_level(path):
        if elem.tag != OWL + "Class":
            continue
        about = elem.get(RDF + "about") or ""
        if not about.startswith(OBO_IRI + subject_prefix + "_"):
            continue
        subject = about[len(OBO_IRI) :].replace("_", ":", 1)
        if elem.find(OWL + "deprecated") is not None:
            continue
        for restr in elem.iter(OWL + "Restriction"):
            prop = restr.find(OWL + "onProperty")
            target = restr.find(OWL + "someValuesFrom")
            if prop is None or target is None or prop.get(RDF + "resource") != prop_iri:
                continue
            iri = target.get(RDF + "resource") or ""
            if iri.startswith(OBO_IRI):
                out.append((subject, iri[len(OBO_IRI) :].replace("_", ":", 1)))
    return out


def ontology_version(path: Path) -> str:
    """owl:versionIRI (o versionInfo) dell'header."""
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == OWL + "Ontology":
            iri = elem.find(OWL + "versionIRI")
            if iri is not None and iri.get(RDF + "resource"):
                return str(iri.get(RDF + "resource"))
            info = elem.findtext(OWL + "versionInfo")
            if info:
                return str(info)
            break
    raise LookupError(f"{path.name} senza versione")
