# Come riprendere il lavoro su ATLAS

Per un agente di coding (o per te) che apre una nuova sessione. Leggi prima `SPEC.md`:
contiene gli invarianti non negoziabili. Questo file dice a che punto siamo.

## Stato (13 novembre 2026, sera)

Fatto e sul branch `main`:

- **Fase 0**: proiettile tracciante (fegato → db → API → scena 3D).
- **Fase 1**: pipeline `pipeline/01…04` per BodyParts3D, FMA, UBERON, HPO, HPOA, MONDO,
  Disease Ontology, ICD-11. Il database ha 1.368 strutture.
- **Corpo intero** (SPEC Fase 7 anticipata): 6 regioni (testa, collo, torace, addome,
  arti superiori, arti inferiori), 838 strutture in scena, definite dalla tabella
  `REGIONS` in `pipeline/lib/config.py`.
- **Ereditarietà destra/sinistra**: "Right humerus" eredita i dati di "Humerus",
  dichiarandolo nella scheda e citando la fonte.
- **Interfaccia**: scena 3D, ricerca, `flyTo`, "Mostra solo questo", pagina `/attribution`.
- **Test**: 53 Python (`pytest`), 14 web (`vitest`); ruff, mypy, tsc, eslint puliti.

Sul branch `claude/funny-franklin-2ikacr` (non ancora su `main`), scritto in una
sessione cloud **senza accesso alle fonti** (rete bloccata): codice e test unitari
passano (78 Python, di cui 46 saltati senza dati; 22 web), ma **nulla è stato
verificato sui dati reali**.

- **Ereditarietà dalla classe più generale** (`fma_is_a`, `pipeline/lib/taxonomy.py`):
  per le strutture ancora senza contenuto clinico, l'antenato FMA più vicino che ne ha.
- **Nomi italiani da Wikidata** via FMA ID (P1402, CC0), solo legami uno a uno
  (`pipeline/lib/wikidata.py`); la scheda cita la voce Wikidata.
- **Fenotipi bilaterali** esclusi dalle strutture con un lato (`phenotype.bilateral`,
  `structure.sided`).
- **Fase 2, parte mancante**: strati pelle → muscoli → ossa → organi (tessuto da FMA,
  `structure.tissue`), contorno sulla struttura selezionata, riquadro di misura con
  `?perf`. Provati su una scena sintetica in un browser senza GPU: strati e contorno
  funzionano; gli fps lì non contano.
- `pip install -e` funziona su un clone pulito.

Non fatto: Fasi 3–6 della SPEC (documenti, assistente con citazioni, sintomo → corpo,
Europe PMC).

## Da fare per primo: verificare sui dati reali

```bash
git fetch origin && git checkout claude/funny-franklin-2ikacr
.venv/Scripts/pip install -e ".[dev]"
npm run pipeline        # 01 scarica anche la query Wikidata; 03 e 04 vanno rieseguiti
PYTHONUTF8=1 .venv/Scripts/pytest -q    # i test sui dati non devono più essere saltati
```

Poi leggere:
- `data/reports/is_a_links.md`: la tabella "Antenati usati" in cima. Se compaiono
  antenati troppo generici (tipo "Organ", "Muscle organ", "Artery"), abbassare
  `ISA_MAX_DESCENDANTS` (ora 300) o `ISA_MAX_HOPS` (ora 3) in `pipeline/lib/config.py`
  e rieseguire `npm run pipeline:bridge`.
- `data/reports/coverage.md`: le colonne "+ lato" e "+ classe generale" dicono quanto
  hanno reso le due ereditarietà.
- l'output di 03: quanti nomi italiani da Wikidata e quanti scartati per ambiguità.
- alcune schede nel browser: un osso o un muscolo con lato, per controllare la nota
  "classe più generale" e il nome italiano.
- l'output di 04: "tessuti (livelli della scena)" e gli eventuali avvisi "classe FMA per
  i tessuti non trovata". Se un nome di `TISSUE_CLASSES` non esiste in FMA, correggerlo
  con il nome preferito che FMA usa davvero.
- **chiusura della Fase 2**: aprire `http://localhost:5173/?perf`, ruotare e
  ingrandire per qualche secondo, leggere il riquadro (obiettivi: caricamento < 3 s,
  ~60 fps). Provare gli strati e il `flyTo` su strutture piccole e grandi.

Le soglie di `test_bilateral_phenotypes_and_sided_structures_are_marked` (>50, >100)
sono stime: se il test fallisce, controllare prima i numeri reali.

## Problemi aperti, in ordine di valore

1. **Copertura clinica bassa**: collo 68%, addome 43%, testa 30%, torace 25%, arti
   inferiori 10%, arti superiori 2% (strutture con legame UBERON esatto). L'ereditarietà
   ha aiutato, ma restavano ~700 strutture senza dati. Ora c'è anche `fma_is_a`: da
   misurare (vedi sopra). Vedi `data/reports/coverage.md`.
2. **Nomi italiani quasi assenti** (FMA ne ha 8 su 1.368). Ora c'è Wikidata: da misurare.
3. **Polmoni senza superficie** in BodyParts3D 4.0 (solo vie bronchiali e vasi).
4. ~~**Fenotipi "bilateral"** su strutture con un solo lato~~: corretto, da verificare.
5. **Validazione clinica**: serve una persona con formazione medica prima di rendere
   pubblica l'app (SPEC §13). Il repository deve restare **privato**.

## Come rimettere in piedi l'ambiente

Su un computer nuovo (Windows; `make` non serve):

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
npm install
npm --prefix web install
npm run pipeline        # scarica ~600 MB e produce data/atlas.db + data/meshes/*.glb
npm run dev             # API :8000 + web :5173 → http://localhost:5173
```

`data/` non è su git (è rigenerabile). Servono Python 3.11+ e Node 20+.

## Controlli prima di ogni commit

```bash
.venv/Scripts/ruff check api pipeline tests
.venv/Scripts/mypy api pipeline
PYTHONUTF8=1 .venv/Scripts/pytest -q
npm --prefix web run typecheck && npm --prefix web run lint && npm --prefix web test
```

Se cambi l'API, rigenera i tipi con l'API accesa: `npm run gen:types`.

## Regole di lavoro che valgono qui

- **Non inventare ID** (FMA, UBERON, HPO, MONDO, ICD-11): vengono dai file scaricati.
  Ciò che manca va in `unmapped`.
- **Ogni affermazione clinica cita una fonte apribile** (invariante I2).
- Nessuna parola come "diagnosi" o "probabilmente hai" nell'interfaccia (SPEC §9).
- Commit convenzionali con scope = fase. Dopo il pipeline, leggere `data/reports/`.
- Su Windows: eseguire Python con `PYTHONUTF8=1`; nel bash di Git gli heredoc con `'''`
  si rompono (scrivere i file con l'editor); l'API parte senza `--reload`
  (`npm run dev:api:reload` solo in un terminale separato).
- Più dettagli e scelte documentate: `README.md`, `SPEC.md`.

## Prossimo passo suggerito

Verificare sui dati quanto sopra e leggere le misure di Fase 2: se i criteri passano,
la Fase 2 è chiusa. Poi Fase 3 (documenti con licenza, SPEC §10): chiedere conferma
sulle scelte di fonte e licenza prima di scrivere codice.
