"""01 — Scarica BodyParts3D e i file ontologici in data/raw/.

Idempotente: un file già presente non viene riscaricato (usare --force per farlo).
Ogni download viene registrato in data/raw/MANIFEST.json con URL, data, dimensione
e SHA-256, così si sa sempre da quale versione nasce atlas.db.

Uso:  python -m pipeline.01_fetch_sources [--force]
"""

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from pipeline.lib import config

USER_AGENT = "atlas-pipeline/0.1 (+offline ETL; anatomy education)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)
    tmp.replace(dest)


def load_manifest() -> dict[str, dict[str, object]]:
    if config.MANIFEST.exists():
        data: dict[str, dict[str, object]] = json.loads(config.MANIFEST.read_text("utf-8"))
        return data
    return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="riscarica anche i file presenti")
    args = parser.parse_args()

    manifest = load_manifest()
    for src in config.SOURCES:
        key = src.dest.relative_to(config.RAW).as_posix()
        if src.dest.exists() and not args.force:
            print(f"  = {key}")
        else:
            print(f"  ↓ {key}  ←  {src.url}")
            download(src.url, src.dest)
        if (
            key not in manifest
            or args.force
            or manifest[key].get("bytes") != src.dest.stat().st_size
        ):
            manifest[key] = {
                "url": src.url,
                "retrieved": dt.date.today().isoformat(),
                "bytes": src.dest.stat().st_size,
                "sha256": sha256(src.dest),
            }

    # ICD-11: la tabulazione arriva zippata
    if not config.ICD11_TABULATION.exists():
        with zipfile.ZipFile(config.ICD11_ZIP) as zf:
            zf.extract(config.ICD11_TABULATION.name, config.ICD11_DIR)
    config.ICD11_RELEASE_FILE.write_text(config.ICD11_RELEASE + "\n", encoding="utf-8")

    config.MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"OK: {len(config.SOURCES)} fonti, manifest in {config.MANIFEST.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
