# ATLAS

Atlante anatomico 3D con ragionamento clinico assistito. Il brief completo è in
[SPEC.md](SPEC.md): va letto prima di scrivere codice.

**Stato:** corpo intero in sei regioni (testa, collo, torace, addome con pelvi, arti
superiori, arti inferiori), 838 strutture nella scena. Ogni scheda elenca patologie
(MONDO, con codice ICD-11 quando esiste) e segni (HPO), ciascuno con il rimando alla
fonte. Clic o ricerca portano la camera sulla struttura (`flyTo`); "Mostra solo questo"
la isola. La copertura clinica è disomogenea tra regioni: vedi `data/reports/coverage.md`.

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
scaricati finisce in `unmapped` (invariante I5). **Dopo ogni esecuzione vanno letti
`data/reports/coverage.md` e `data/reports/unmapped_<regione>.md`.**

### Scelte di Fase 1 da conoscere

- **Regioni: una tabella, non codice.** `REGIONS` in `pipeline/lib/config.py` elenca
  le regioni in ordine di priorità. Testa, collo, arti e torace sono definiti dai loro
  concetti BodyParts3D; l'addome da un volume (box di *abdomen* `FMA:9577`, che include
  la pelvi, sotto il diaframma `FMA:13295`). Ciò che nessuna regola reclama (vasi,
  nervi) segue l'elemento reclamato più vicino. Ogni regione produce un GLB; aggiungerne
  una non richiede modifiche all'applicazione.
- **Un nodo sta in un solo GLB.** Un concetto i cui elementi cadono in due regioni va
  nella regione della maggioranza: ogni FMA ID compare in un solo file.
- **Ereditarietà destra/sinistra.** Le fonti cliniche parlano di "omero", non di
  "omero destro". Una struttura con lato eredita i legami UBERON della versione senza
  lato solo se la fonte dichiara la sottoclasse (FMA `subClassOf`, UBERON `is_a`) e i
  nomi coincidono a meno del lato (`pipeline/lib/laterality.py`). I legami stanno in
  `structure_uberon` con la loro provenienza; `structure.uberon_id` resta il solo xref
  esatto. La scheda lo dichiara e cita la relazione. Effetto sulle strutture con almeno
  una patologia o un segno: arti superiori 2 → 63, arti inferiori 3 → 57, testa
  43 → 123, torace 35 → 57, addome 52 → 66.
- **Fonte della sede.** `disease_structure.source` dice chi asserisce che una malattia
  ha sede in una struttura (MONDO o Disease Ontology); la scheda cita quella fonte.
- **Apparato (`system`).** Dall'albero di BodyParts3D quando lo dichiara; altrimenti
  risalendo il `part_of` di FMA (es. cuore, cervelletto, che BodyParts3D colloca sotto
  "torace" e "testa").
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
- **Estensioni allo schema di SPEC §6:** tabelle `source_release` (versione e licenza
  di ogni fonte) e `structure_uberon` (legami con provenienza), colonne
  `disease_structure.source/source_id`, indici sulle tabelle di relazione.

## Sviluppo

```bash
npm run dev                  # API su :8000 + web su :5173  (equivale a `make dev`)
npm run gen:types            # rigenera web/src/types/atlas.d.ts dall'OpenAPI (API accesa)
```

L'API parte senza riavvio automatico: su Windows il reloader di uvicorn manda un Ctrl+C
a tutta la console e spegne anche il server web. Chi modifica `api/` può usare
`npm run dev:api:reload` in un terminale a parte.

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
