"""07 — Chunk dei documenti ed embedding locali in sqlite-vec.

1. I documenti senza chunk (nuovi, o con testo cambiato: 05 ne butta i chunk) vengono
   divisi in chunk (pipeline/lib/chunking.py).
2. I chunk senza vettore ricevono l'embedding del modello config.EMBED_MODEL, calcolato
   in locale (GPU se c'è): nessun testo esce dalla macchina (SPEC §4). Il testo passato
   al modello è "passage: <titolo del documento>. <chunk>", come vuole E5.
3. Ogni documento riceve anche un vettore del solo titolo (`title_vec`): la ricerca
   guarda titoli e chunk insieme.
4. Ogni fenotipo HPO che /locate può usare (ha un legame a una struttura, calcolato da
   04) riceve un vettore per il nome e per ciascun sinonimo (`phenotype_vec`): i
   sinonimi di HPO comprendono le forme in linguaggio comune ("Blood in urine"). Qui il
   prefisso E5 è "query: " anche per i nomi: domanda e nome sono frasi brevi da
   confrontare tra loro, il caso simmetrico per cui la scheda del modello lo prescrive.
   Modello proprio, config.LOCATE_MODEL (più grande: vedi il commento in config).
5. I vettori di chunk, documenti e fenotipi non più esistenti vengono rimossi.

Riprendibile: salva a lotti; interrotto, riparte dai chunk ancora senza vettore.
Cambiare modello rifà tutti i vettori.

Prova rapida senza GPU: `--first-chunks 1` indicizza solo il primo chunk di ogni
documento (l'introduzione di ogni capitolo, ogni definizione): la ricerca funziona ma
non vede il resto dei testi. Rieseguire senza l'opzione completa l'indice.

Richiede le dipendenze opzionali:  pip install -e ".[embed]"
Uso:  python -m pipeline.07_embed [--model NOME] [--device cuda|cpu] [--sources a,b]
"""

import argparse
import sqlite3
import sys
import time

from pipeline.lib import chunking, config, db, vec

BATCH = 256  # chunk per scrittura su disco


def make_chunks(conn: sqlite3.Connection, sources: set[str] | None) -> int:
    rows: list[tuple[str, str, int, str]] = []
    for doc_id, text in db.documents_without_chunks(conn):
        if sources and doc_id.split(":", 1)[0] not in sources:
            continue
        for i, piece in enumerate(chunking.chunk_text(text, config.CHUNK_CHARS)):
            rows.append((f"{doc_id}#{i}", doc_id, i, piece))
    db.insert_chunks(conn, rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=config.EMBED_MODEL)
    parser.add_argument("--locate-model", default=config.LOCATE_MODEL)
    parser.add_argument("--device", default=None, help="cuda | cpu (predefinito: automatico)")
    parser.add_argument("--sources", default="", help="solo queste fonti, separate da virgola")
    parser.add_argument("--max-minutes", type=float, default=0, help="fermati dopo N minuti")
    parser.add_argument(
        "--first-chunks", type=int, default=0, help="solo i primi N chunk di ogni documento"
    )
    args = parser.parse_args()
    sources = {s for s in args.sources.split(",") if s} or None

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        sys.exit('manca sentence-transformers: pip install -e ".[embed]"')

    # Prima del caricamento (che alla prima esecuzione scarica ~1 GB e non stampa nulla):
    # si dice subito se la scheda video è visibile, perché sulla CPU ci vogliono ore.
    import torch

    gpu = torch.cuda.is_available()
    print(
        f"  torch {torch.__version__}; scheda video: "
        f"{torch.cuda.get_device_name(0) if gpu else 'NON trovata'}"
    )
    if not gpu and args.device in (None, "cuda"):
        print(
            "  ATTENZIONE: senza scheda video questo passo richiede ore. Su Windows "
            "pip installa torch solo per CPU: vedi README (torch con CUDA)."
        )
    print(
        f"  carico {args.model} (la prima volta scarica ~1 GB: può non stampare "
        "nulla per qualche minuto)...",
        flush=True,
    )
    model = SentenceTransformer(args.model, device=args.device)
    # sentence-transformers ≥ 6 ha rinominato il metodo
    get_dim = (
        getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    )
    dim = int(get_dim() or 0)
    print(f"  modello {args.model} ({dim} dimensioni) su {model.device}")

    conn = db.connect(config.DB_PATH)
    vec.load(conn)
    with conn:
        db.migrate(conn)
        made = make_chunks(conn, sources)
        if vec.ensure(conn, args.model, dim):
            print("  modello cambiato: i vettori precedenti sono stati rimossi")
        removed = vec.delete_orphans(conn)
    print(f"  chunk nuovi: {made}; vettori orfani rimossi: {removed}")

    started = time.monotonic()
    done = 0
    while True:
        batch = vec.chunks_without_vectors(conn, BATCH * 8, sources, args.first_chunks)
        if not batch:
            break
        for i in range(0, len(batch), BATCH):
            part = batch[i : i + BATCH]
            vectors = model.encode(
                [f"passage: {title}. {text}" for _cid, title, text in part],
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            with conn:
                vec.insert(
                    conn,
                    [(cid, v.tolist()) for (cid, _t, _x), v in zip(part, vectors, strict=True)],
                )
            done += len(part)
        left = vec.missing_count(conn)
        rate = done / max(time.monotonic() - started, 1e-6)
        print(f"  {done} vettori ({rate:.1f}/s); ne mancano {left}", flush=True)
        if args.max_minutes and time.monotonic() - started > args.max_minutes * 60:
            print("  tempo scaduto: rieseguire per continuare")
            break
    titled = 0
    out_of_time = bool(args.max_minutes and time.monotonic() - started > args.max_minutes * 60)
    while not out_of_time and (batch_t := vec.titles_without_vectors(conn, BATCH * 8, sources)):
        vectors = model.encode(
            [f"passage: {title}" for _doc, title in batch_t],
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        with conn:
            vec.insert_titles(
                conn,
                [(doc, t, v.tolist()) for (doc, t), v in zip(batch_t, vectors, strict=True)],
            )
        titled += len(batch_t)
        print(f"  {titled} titoli", flush=True)
        if args.max_minutes and time.monotonic() - started > args.max_minutes * 60:
            print("  tempo scaduto: rieseguire per continuare")
            break
    with conn:
        names = db.phenotypes_to_embed(conn)
    if names:
        locate_model = (
            model
            if args.locate_model == args.model
            else SentenceTransformer(args.locate_model, device=args.device)
        )
        get_ldim = (
            getattr(locate_model, "get_embedding_dimension", None)
            or locate_model.get_sentence_embedding_dimension
        )
        with conn:
            if vec.ensure_phenotypes(conn, args.locate_model, int(get_ldim() or 0)):
                print("  modello dei fenotipi cambiato: vettori precedenti rimossi")
            todo = vec.phenotypes_to_refresh(conn, names)
        print(f"  fenotipi: modello {args.locate_model}; nomi da indicizzare {len(todo)}")
        for i in range(0, len(todo), BATCH * 8):
            part_p = todo[i : i + BATCH * 8]
            vectors = locate_model.encode(
                [f"query: {text}" for _h, text in part_p],
                batch_size=64,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            with conn:
                vec.insert_phenotypes(
                    conn, [(h, t, v.tolist()) for (h, t), v in zip(part_p, vectors, strict=True)]
                )
            print(f"  {i + len(part_p)} nomi di fenotipo", flush=True)
    total = conn.execute("SELECT COUNT(*) FROM chunk_vec").fetchone()[0]
    titles = conn.execute("SELECT COUNT(*) FROM title_vec").fetchone()[0]
    phenos = conn.execute("SELECT COUNT(*) FROM phenotype_vec").fetchone()[0]
    conn.close()
    print(f"OK: {total} vettori in chunk_vec, {titles} in title_vec, {phenos} in phenotype_vec")
    return 0


if __name__ == "__main__":
    sys.exit(main())
