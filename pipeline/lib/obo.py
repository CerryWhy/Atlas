"""Parser OBO minimale: quanto basta per leggere stanze [Term] di MONDO e UBERON."""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

_DEF_RE = re.compile(r'^"((?:[^"\\]|\\.)*)"')


@dataclass
class Term:
    id: str
    name: str = ""
    definition: str | None = None
    obsolete: bool = False
    xrefs: list[str] = field(default_factory=list)
    # sottoinsieme di xrefs che MONDO marca come equivalenza esatta (MONDO:equivalentTo)
    equivalent_xrefs: list[str] = field(default_factory=list)
    # (relazione, target) da righe `relationship:` e `intersection_of:` con relazione
    relations: list[tuple[str, str]] = field(default_factory=list)


def _strip_comment(value: str) -> str:
    value = value.split(" ! ", 1)[0]
    return re.sub(r"\s*\{.*\}\s*$", "", value).strip()


def iter_terms(path: Path) -> Iterator[Term]:
    term: Term | None = None
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("["):
                if term is not None:
                    yield term
                term = None
                if line == "[Term]":
                    term = Term(id="")
                continue
            if term is None or ": " not in line:
                continue
            tag, value = line.split(": ", 1)
            if tag == "id":
                term.id = value.strip()
            elif tag == "name":
                term.name = value.strip()
            elif tag == "def":
                m = _DEF_RE.match(value)
                term.definition = m.group(1).replace('\\"', '"') if m else None
            elif tag == "is_obsolete":
                term.obsolete = value.strip() == "true"
            elif tag == "xref":
                xref = _strip_comment(value).split(" ", 1)[0]
                term.xrefs.append(xref)
                if 'source="MONDO:equivalentTo"' in value:
                    term.equivalent_xrefs.append(xref)
            elif tag in ("relationship", "intersection_of"):
                parts = _strip_comment(value).split()
                if len(parts) == 2:
                    term.relations.append((parts[0], parts[1]))
    if term is not None:
        yield term


def data_version(path: Path) -> str:
    """Valore dell'header `data-version:` del file OBO."""
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("data-version:"):
                return line.split(":", 1)[1].strip()
            if line.startswith("["):
                break
    raise LookupError(f"{path.name} senza data-version")


def license_url(path: Path) -> str:
    """URL di licenza dichiarato nell'header (terms:license / dcterms-license)."""
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("["):
                break
            if line.startswith("property_value:") and "license" in line.split()[1]:
                return line.split()[2].strip('"')
    raise LookupError(f"{path.name} non dichiara una licenza")


def load_terms(path: Path, ids: set[str] | None = None) -> dict[str, Term]:
    return {t.id: t for t in iter_terms(path) if ids is None or t.id in ids}
