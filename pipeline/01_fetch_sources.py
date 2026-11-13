"""01 — Scarica BodyParts3D e i file ontologici in data/raw/.

Idempotente: un file già presente non viene riscaricato (usare --force per farlo).
Ogni download viene registrato in data/raw/MANIFEST.json con URL, data, dimensione
e SHA-256, così si sa sempre da quale versione nasce atlas.db (pipeline/lib/fetch.py).

Uso:  python -m pipeline.01_fetch_sources [--force]
"""

import argparse
import sys
import zipfile

from pipeline.lib import config, fetch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="riscarica anche i file presenti")
    args = parser.parse_args()

    fetch.sync(config.SOURCES, force=args.force)

    # ICD-11: la tabulazione arriva zippata
    if not config.ICD11_TABULATION.exists():
        with zipfile.ZipFile(config.ICD11_ZIP) as zf:
            zf.extract(config.ICD11_TABULATION.name, config.ICD11_DIR)
    config.ICD11_RELEASE_FILE.write_text(config.ICD11_RELEASE + "\n", encoding="utf-8")

    print(f"OK: {len(config.SOURCES)} fonti, manifest in {config.MANIFEST.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
