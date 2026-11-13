"""Download e MANIFEST condivisi dagli script che scaricano (01, 05).

Ogni file scaricato è registrato in data/raw/MANIFEST.json con l'URL usato davvero,
la data, la dimensione e lo SHA-256: si sa sempre da quale versione nasce atlas.db.
"""

import datetime as dt
import hashlib
import json
import shutil
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


def download(url: str, dest: Path, timeout: int = 120) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
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
