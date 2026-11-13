# ATLAS

Atlante anatomico 3D con ragionamento clinico assistito. Il brief completo è in
[SPEC.md](SPEC.md): va letto prima di scrivere codice.

**Stato:** Fase 1 chiusa (pipeline ontologica, regione addominale). La scena mostra
l'addome con 214 strutture; ogni scheda elenca patologie (MONDO, con codice ICD-11
quando esiste) e segni (HPO), ciascuno con il rimando alla fonte.

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

## Pipeline → `data/atlas.db` + `data/meshes/*.glb`

```bash
npm run pipeline             # tutti i passi, in ordine
```

| Passo | Script | Cosa fa |
|---|---|---|
| `npm run pipeline:fetch` | `pipeline/01_fetch_sources.py` | Scarica le fonti in `data/raw/` e registra URL, data e SHA-256 in `MANIFEST.json` |
| `npm run pipeline:meshes` | `pipeline/02_build_meshes.py` | OBJ → GLB Draco della regione attiva, centroidi e raggi (`data/build/geometry.json`) |
| `npm run pipeline:ontologies` | `pipeline/03_load_ontologies.py` | FMA, HPO, HPOA, MONDO, Disease Ontology, ICD-11 → tabelle |
| `npm run pipeline:bridge` | `pipeline/04_bridge_fma_uberon.py` | Crosswalk FMA ↔ UBERON, tabella `unmapped`, report in `data/reports/` |

Ogni script è idempotente. Nessun ID viene costruito: ciò che non si trova nei file
scaricati finisce in `unmapped` (invariante I5). **Dopo ogni esecuzione va letto
`data/reports/unmapped_<regione>.md`.**

### Scelte di Fase 1 da conoscere

- **Confine della regione: geometrico.** L'albero di BodyParts3D è organizzato per
  sistemi, non per regioni. Un elemento mesh è "addome" se la maggior parte dei suoi
  vertici cade nel box del concetto FMA *abdomen* (`FMA:9577`, che in FMA comprende
  la pelvi) e non poggia sopra il diaframma (`FMA:13295`). Parametri in
  `pipeline/lib/config.py`.
- **Un nodo GLB per elemento, sotto il concetto più specifico.** Gli insiemi di
  elementi dei concetti si sovrappongono (un segmento epatico è anche "fegato"):
  ogni elemento compare una volta, sotto il concetto più specifico che lo contiene.
  Il fegato non ha quindi un nodo proprio: si accende tramite le sue parti
  (`mesh_nodes` in `GET /structure/{fma_id}`).
- **`parent_fma_id` viene dall'albero PART-OF di BodyParts3D**, che è derivato da FMA
  ed è un albero vero (un solo genitore). Dove FMA 5.1 non asserisce quella relazione
  come parte diretta, la riga è in `unmapped` (`parent_not_direct_fma_part`).
- **Nomi latini e italiani** vengono dagli equivalenti di FMA con lingua dichiarata.
  L'italiano è quasi assente nella fonte: l'interfaccia mostra il nome inglese
  quando manca, non una traduzione fatta a mano.
- **Estensioni allo schema di SPEC §6:** tabella `source_release` (versione e licenza
  di ogni fonte) e tre indici sulle tabelle di relazione.

## Sviluppo

```bash
npm run dev                  # API su :8000 + web su :5173  (equivale a `make dev`)
npm run gen:types            # rigenera web/src/types/atlas.d.ts dall'OpenAPI (API accesa)
```

Variabili opzionali: `ATLAS_API_KEY` (API) + `VITE_ATLAS_API_KEY` (web),
`ATLAS_CORS_ORIGINS`, `ATLAS_DB`, `ATLAS_MESHES`.

### Interfaccia

Il linguaggio visivo è quello della tavola anatomica: scena sul verde dei teli
chirurgici, scheda chiara, un solo accento (iodio), linea di richiamo dall'organo
al suo nome. I token sono in `web/src/index.css`; le tinte dei tessuti e le modalità
di gruppo (pieno, velato, nascosto) in `web/src/scene/tissues.ts`. I caratteri
(Brygada 1918, Hanken Grotesk, entrambi SIL OFL) sono serviti in locale: nessuna
richiesta a terzi.

## Qualità

```bash
.venv/Scripts/ruff check api pipeline tests
.venv/Scripts/mypy api pipeline
.venv/Scripts/pytest         # include i test sui dati: criteri di accettazione di Fase 1
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web test
```
