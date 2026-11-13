"""Download e MANIFEST condivisi dagli script che scaricano (01, 05).

Ogni file scaricato è registrato in data/raw/MANIFEST.json con l'URL usato davvero,
la data, la dimensione e lo SHA-256: si sa sempre da quale versione nasce atlas.db.
"""

import datetime as dt
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from pipeline.lib import config

USER_AGENT = "atlas-pipeline/0.1 (+offline ETL; anatomy education)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


PROGRESS_STEP = 50 << 20  # una riga di avanzamento ogni 50 MB


def download(url: str, dest: Path, timeout: int = 120) -> None:
    """Scarica in `<dest>.part` e lo rinomina a fine corsa. Se il `.part` esiste (download
    interrotto) riprende da lì con l'intestazione Range, quando il server la accetta;
    altrimenti riparte da zero. Stampa l'avanzamento sui file grandi."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    have = tmp.stat().st_size if tmp.exists() else 0
    headers = {"User-Agent": USER_AGENT}
    if have:
        headers["Range"] = f"bytes={have}-"
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 416 and have:  # il .part non corrisponde al file: da capo
            tmp.unlink()
            return download(url, dest, timeout)
        raise
    with resp:
        resuming = have > 0 and resp.status == 206
        done = have if resuming else 0
        length = int(resp.headers.get("Content-Length") or 0)
        total = done + length if length else 0
        if resuming:
            print(f"    ripreso da {done >> 20} MB")
        shown = done
        with tmp.open("ab" if resuming else "wb") as out:
            while block := resp.read(1 << 20):
                out.write(block)
                done += len(block)
                if total > PROGRESS_STEP and done - shown >= PROGRESS_STEP:
                    shown = done
                    print(
                        f"    {done >> 20} / {total >> 20} MB ({100 * done // total}%)", flush=True
                    )
    tmp.replace(dest)


def read_text(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(resp.read().decode("utf-8", errors="replace"))


def fetch_first(src: config.Source) -> str:
    """Scarica dall'URL ufficiale o, se non risponde, dalla prima copia che risponde.
    Restituisce l'URL usato davvero (finisce nel MANIFEST)."""
    errors: list[str] = []
    for url in (src.url, *src.mirrors):
        print(f"  ↓ {src.dest.name}  ←  {url}")
        try:
            download(url, src.dest)
            return url
        except OSError as e:  # URLError, HTTPError, timeout
            errors.append(f"{url}: {e}")
            print(f"    non disponibile: {e}")
    raise SystemExit(f"{src.dest.name}: nessuna fonte raggiungibile\n  " + "\n  ".join(errors))


def load_manifest() -> dict[str, dict[str, object]]:
    if config.MANIFEST.exists():
        data: dict[str, dict[str, object]] = json.loads(config.MANIFEST.read_text("utf-8"))
        return data
    return {}


def save_manifest(manifest: dict[str, dict[str, object]]) -> None:
    config.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    config.MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def manifest_key(path: Path) -> str:
    return path.relative_to(config.RAW).as_posix()


def record(manifest: dict[str, dict[str, object]], path: Path, url: str) -> None:
    manifest[manifest_key(path)] = {
        "url": url,
        "retrieved": dt.date.today().isoformat(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def sync(sources: list[config.Source], force: bool = False) -> dict[str, dict[str, object]]:
    """Scarica le fonti mancanti (o tutte con force) e aggiorna il MANIFEST."""
    manifest = load_manifest()
    for src in sources:
        key = manifest_key(src.dest)
        used = str(manifest.get(key, {}).get("url", src.url))
        if src.dest.exists() and not force:
            print(f"  = {key}")
        else:
            used = fetch_first(src)
        entry = manifest.get(key)
        if entry is None or force or entry.get("bytes") != src.dest.stat().st_size:
            record(manifest, src.dest, used)
        save_manifest(manifest)  # dopo ogni file: un'interruzione non perde i precedenti
    return manifest


def retrieved(path: Path) -> str:
    """Data di download dal MANIFEST: per una fonte che cambia ogni giorno è la versione."""
    return str(load_manifest()[manifest_key(path)]["retrieved"])
