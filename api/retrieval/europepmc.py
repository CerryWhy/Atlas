"""Tier 2 (SPEC §8): Europe PMC in tempo reale, solo open access, mai ingerito.

Senza l'assistente (Fase 4 rinviata) la letteratura compare nella scheda di ogni
struttura: articoli open access cercati per nome della struttura nei titoli e negli
abstract, in ordine di rilevanza. Ogni articolo porta la licenza che Europe PMC
dichiara per lui (I3) e un link apribile (I2): la pagina dell'articolo su Europe PMC
(per gli open access, con il testo integrale); il DOI, se c'è, è a parte. Si invia solo
il nome della struttura, mai testo scritto dall'utente (I4); i risultati restano in
memoria per non ripetere la stessa richiesta e non vengono salvati.

API REST pubblica, senza chiave: https://europepmc.org/RestfulWebService
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
USER_AGENT = "atlas/0.1 (anatomy study tool)"
TIMEOUT_S = 10


class LiteratureUnavailable(RuntimeError):
    """Europe PMC non raggiungibile o risposta inattesa."""


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    authors: str
    journal: str | None
    year: str | None
    doi: str | None
    url: str
    license: str  # come la dichiara Europe PMC (es. "cc by"), o "open access" se assente


def query_for(name: str) -> str:
    """Il nome tra virgolette nel titolo o nell'abstract, solo articoli open access."""
    term = name.replace('"', " ").strip()
    return f'(TITLE:"{term}" OR ABSTRACT:"{term}") AND OPEN_ACCESS:y'


def parse(payload: dict[str, Any]) -> tuple[int, list[Article]]:
    """(numero di risultati, articoli) dalla risposta JSON di /search (resultType=core)."""
    total = int(payload.get("hitCount") or 0)
    out: list[Article] = []
    for r in payload.get("resultList", {}).get("result", []):
        if r.get("isOpenAccess") != "Y" or not r.get("title") or not r.get("id"):
            continue
        source, rid = r.get("source", "MED"), str(r["id"])
        doi = r.get("doi")
        journal = (r.get("journalInfo") or {}).get("journal", {}).get("title")
        out.append(
            Article(
                id=f"{source}:{rid}",
                title=str(r["title"]).rstrip("."),
                authors=str(r.get("authorString") or ""),
                journal=journal,
                year=r.get("pubYear"),
                doi=doi,
                url=f"https://europepmc.org/article/{source}/{rid}",
                license=str(r.get("license") or "open access"),
            )
        )
    return total, out


@lru_cache(maxsize=512)
def search(name: str, n: int) -> tuple[int, tuple[Article, ...]]:
    params = urllib.parse.urlencode(
        {"query": query_for(name), "format": "json", "resultType": "core", "pageSize": n}
    )
    req = urllib.request.Request(f"{SEARCH_URL}?{params}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError) as e:  # rete, timeout, HTTP, JSON non valido
        raise LiteratureUnavailable(f"Europe PMC non raggiungibile: {e}") from e
    total, articles = parse(payload)
    return total, tuple(articles)
