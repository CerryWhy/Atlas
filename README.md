# ATLAS

Atlante anatomico 3D con ragionamento clinico assistito. Il brief completo è in
[SPEC.md](SPEC.md): va letto prima di scrivere codice.

**Stato:** Fase 0 (proiettile tracciante) — un fegato cliccabile, tre patologie
reali da MONDO con codice ICD-11, lette da `data/atlas.db`.

## Prerequisiti

- Python 3.11+, Node 20+
- (opzionale) `make`; su Windows usare direttamente gli script `npm run …`

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # POSIX: .venv/bin/pip
npm install
npm --prefix web install
```

## Dati grezzi (`data/raw/`, non versionati)

Scaricare in `data/raw/` (in Fase 1 lo farà `pipeline/01_fetch_sources.py`):

| File | Sorgente |
|---|---|
| `bodyparts3d/partof_BP3D_4.0_obj_99.zip`, `partof_parts_list_e.txt`, `partof_element_parts.txt` | https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/ |
| `ontologies/mondo.obo` | http://purl.obolibrary.org/obo/mondo.obo |
| `ontologies/uberon-basic.obo` | http://purl.obolibrary.org/obo/uberon/basic.obo |
| `icd11/SimpleTabulation-ICD-11-MMS-en.txt` + `icd11/RELEASE` (es. `2026-01`) | https://icdcdn.who.int/static/releasefiles/2026-01/SimpleTabulation-ICD-11-MMS-en.zip |

## Pipeline → artefatti

```bash
npm run pipeline:phase0      # → data/atlas.db + data/meshes/liver.glb (Draco)
```

Lo script fallisce se anche un solo ID (FMA, UBERON, MONDO, ICD-11) non si trova
nei file scaricati (invariante I5).

## Sviluppo

```bash
npm run dev                  # API su :8000 + web su :5173  (equivale a `make dev`)
npm run gen:types            # rigenera web/src/types/atlas.d.ts dall'OpenAPI (API accesa)
```

Variabili opzionali: `ATLAS_API_KEY` (API) + `VITE_ATLAS_API_KEY` (web),
`ATLAS_CORS_ORIGINS`, `ATLAS_DB`, `ATLAS_MESHES`.

## Qualità

```bash
.venv/Scripts/ruff check api pipeline tests
.venv/Scripts/mypy api pipeline
.venv/Scripts/pytest
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web test
```
