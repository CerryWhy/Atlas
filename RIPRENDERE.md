# Come riprendere il lavoro su ATLAS

Per un agente di coding (o per te) che apre una nuova sessione. Leggi prima `SPEC.md`:
contiene gli invarianti non negoziabili. Questo file dice a che punto siamo.

## Stato (13 novembre 2026)

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

Non fatto: Fasi 3–6 della SPEC (documenti, assistente con citazioni, sintomo → corpo,
Europe PMC), pelle/muscoli come livelli, contorno sulla struttura attiva, misura degli
fps (va fatta su uno schermo reale).

## Problemi aperti, in ordine di valore

1. **Copertura clinica bassa**: collo 68%, addome 43%, testa 30%, torace 25%, arti
   inferiori 10%, arti superiori 2% (strutture con legame UBERON esatto). L'ereditarietà
   ha aiutato, ma restano ~700 strutture senza dati. Vedi `data/reports/coverage.md`.
2. **Nomi italiani quasi assenti** (FMA ne ha 8 su 1.368). Candidato non verificato:
   Wikidata via ID FMA (CC0).
3. **Polmoni senza superficie** in BodyParts3D 4.0 (solo vie bronchiali e vasi).
4. **Fenotipi "bilateral"** compaiono su strutture con un solo lato (noto, non corretto).
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

Alzare la copertura clinica (punto 1) prima di aggiungere nuove funzioni; poi Fase 3
(documenti con licenza, SPEC §10). Chiedere conferma sulle scelte di fonte e licenza.
