"""05 — Corpus testuale: MedlinePlus, Orphanet, StatPearls → tabella document.

Cosa viene da dove (pipeline/lib/docsrc.py per i formati):
- MedlinePlus   health topics in inglese (XML giornaliero NLM), pubblico dominio;
                riferimenti: descrittori MeSH dichiarati dal topic.
- Orphanet      definizioni dei disordini (Orphadata en_product1.xml), CC BY 4.0
                dichiarata nel file; riferimenti: ORPHAcode e MONDO esatti (E).
- StatPearls    capitoli dall'archivio NCBI Bookshelf sull'FTP ufficiale (litarch),
                licenza letta capitolo per capitolo; riferimenti: oggetto dei capitoli
                di anatomia ("Anatomy, Abdomen and Pelvis, Liver" → "Liver").

I3: un documento senza licenza riconosciuta non entra; si contano gli scarti.
Idempotente: un documento il cui testo non è cambiato non viene toccato (i suoi
chunk ed embedding restano); i documenti spariti dalla fonte vengono rimossi.

Uso:  python -m pipeline.05_ingest_documents [--force] [--only medlineplus,orphanet,...]
"""

import argparse
import csv
import hashlib
import io
import re
import sqlite3
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

from pipeline.lib import config, db, docsrc, fetch

Reader = Callable[[Path, docsrc.ReadStats], Iterator[docsrc.Doc]]


def medlineplus_url() -> str:
    page = fetch.read_text(config.MEDLINEPLUS_INDEX)
    links = sorted(
        set(re.findall(r"https://medlineplus\.gov/xml/mplus_topics_\d{4}-\d\d-\d\d\.xml", page))
    )
    if not links:
        raise SystemExit(f"nessun mplus_topics_<data>.xml in {config.MEDLINEPLUS_INDEX}")
    return str(links[-1])  # la data più recente


def statpearls_url() -> str:
    listing = fetch.read_text(config.NCBI_LITARCH + "file_list.csv", timeout=120)
    for row in csv.DictReader(io.StringIO(listing)):
        if row.get("Accession ID") == config.STATPEARLS_ACCESSION:
            return config.NCBI_LITARCH + row["File"]
    raise SystemExit(f"{config.STATPEARLS_ACCESSION} assente da file_list.csv")


SOURCES: dict[str, tuple[Path, Callable[[], str], Reader, tuple[str, str, str, str]]] = {
    # nome: (file, url, lettore, (titolo, url pubblico, licenza, attribuzione))
    "medlineplus": (
        config.MEDLINEPLUS_XML,
        medlineplus_url,
        docsrc.read_medlineplus,
        (
            "MedlinePlus Health Topics",
            "https://medlineplus.gov/xml.html",
            docsrc.MEDLINEPLUS_LICENSE,
            "MedlinePlus health topic summaries, U.S. National Library of Medicine "
            "(public domain; https://medlineplus.gov/about/using/usingcontent/).",
        ),
    ),
    "orphanet": (
        config.ORPHANET_XML,
        lambda: config.ORPHANET_URL,
        docsrc.read_orphanet,
        (
            "Orphanet — rare disease definitions (Orphadata)",
            "https://sciences.orphadata.com/",
            "CC BY 4.0",
            "Orphanet: an online database of rare diseases and orphan drugs. "
            "© INSERM 1997. Orphadata, licensed under CC BY 4.0.",
        ),
    ),
    "statpearls": (
        config.STATPEARLS_TGZ,
        statpearls_url,
        docsrc.read_statpearls,
        (
            "StatPearls (NCBI Bookshelf)",
            f"https://www.ncbi.nlm.nih.gov/books/{config.STATPEARLS_ACCESSION}/",
            "CC BY-NC-ND 4.0",
            "StatPearls, StatPearls Publishing, Treasure Island (FL), via NCBI Bookshelf. "
            "Licensed under CC BY-NC-ND 4.0; chapters reproduced without modification.",
        ),
    ),
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest(c: sqlite3.Connection, name: str, path: Path, reader: Reader, retrieved: str) -> None:
    stats = docsrc.ReadStats()
    known = db.document_hashes(c, name)
    seen: set[str] = set()
    changed = 0
    for doc in reader(path, stats):
        seen.add(doc.doc_id)
        digest = sha(doc.text)
        if known.get(doc.doc_id) != digest:
            changed += 1
            db.delete_document_dependents(c, [doc.doc_id])
        db.upsert_document(
            c,
            (doc.doc_id, name, doc.title, doc.url, doc.license, retrieved, doc.text, digest),
        )
        db.replace_document_refs(c, doc.doc_id, doc.refs)
    gone = set(known) - seen
    db.delete_documents(c, gone)
    print(
        f"  {name}: {stats.read} documenti ({changed} nuovi o cambiati, {len(gone)} rimossi);"
        f" scartati: licenza {stats.skipped_license}, vuoti {stats.skipped_empty},"
        f" altro {stats.skipped_other}; licenze {dict(sorted(stats.licenses_seen.items()))}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="riscarica le fonti")
    parser.add_argument("--only", default=",".join(SOURCES), help="fonti, separate da virgola")
    args = parser.parse_args()
    names = [n for n in args.only.split(",") if n]
    unknown = set(names) - set(SOURCES)
    if unknown:
        sys.exit(f"fonti sconosciute: {sorted(unknown)}")

    for name in names:
        path, find_url, _reader, _meta = SOURCES[name]
        known = fetch.manifest_key(path) in fetch.load_manifest()
        if args.force or not path.exists() or not known:
            fetch.sync([config.Source(path, find_url())], force=True)
        else:
            print(f"  = {fetch.manifest_key(path)}")

    conn = db.connect(config.DB_PATH)
    with conn:
        db.migrate(conn)
        for name in names:
            path, _find, reader, (title, page, lic, attribution) = SOURCES[name]
            when = fetch.retrieved(path)
            ingest(conn, name, path, reader, when)
            db.upsert_source_release(conn, name, title, when, page, lic, attribution)
    total = conn.execute("SELECT source, COUNT(*) FROM document GROUP BY source").fetchall()
    conn.close()
    print(f"OK: documenti per fonte {dict(total)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
