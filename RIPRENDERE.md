# Come riprendere il lavoro su ATLAS

Per un agente di coding (o per te) che apre una nuova sessione. Leggi prima `SPEC.md`:
contiene gli invarianti non negoziabili. Questo file dice a che punto siamo.

## Stato (14 novembre 2026)

Sul branch `main`:

- **Fase 0**: proiettile tracciante (fegato → db → API → scena 3D).
- **Fase 1**: pipeline `pipeline/01…04` per BodyParts3D, FMA, UBERON, HPO, HPOA, MONDO,
  Disease Ontology, ICD-11. Il database ha 1.368 strutture.
- **Corpo intero** (SPEC Fase 7 anticipata): 6 regioni, 838 strutture in scena,
  definite dalla tabella `REGIONS` in `pipeline/lib/config.py`.
- **Ereditarietà destra/sinistra**, **interfaccia** (scena 3D, ricerca, `flyTo`,
  "Mostra solo questo", `/attribution`).

Sul branch `claude/funny-franklin-2ikacr` (non ancora su `main`), scritto in una
sessione cloud:

- **Copertura clinica**: ereditarietà dalla classe FMA più generale (`fma_is_a`,
  `pipeline/lib/taxonomy.py`), nomi italiani da Wikidata (P1402, CC0), fenotipi
  bilaterali esclusi dalle strutture con un lato.
- **Fase 2 — chiusa per decisione dell'utente**, con una verifica ancora da fare su
  uno schermo reale (vedi sotto): strati pelle → muscoli → ossa → organi (tessuto da
  FMA, `structure.tissue`), contorno sulla struttura selezionata, riquadro `?perf`.
- **Fase 3 — corpus testuale** (fonti confermate dall'utente: StatPearls, MedlinePlus,
  Orphanet):
  - `05_ingest_documents.py`: 16.573 documenti, tutti con licenza (MedlinePlus 1.014
    pubblico dominio; Orphanet 6.898 CC BY 4.0; StatPearls 8.661, di cui 8.660
    CC BY-NC-ND 4.0 e 1 CC BY 4.0, letta capitolo per capitolo).
  - `06_link_documents.py`: legami documento → malattia e → struttura solo da
    riferimenti dichiarati (`pipeline/lib/doclinks.py`), con `basis` e `via`.
  - `07_embed.py`: chunk ed embedding locali in `sqlite-vec`; `GET /search`; la scheda
    ha la voce "Letture".

**Cosa è stato verificato sui dati veri qui, e cosa no.** Questo ambiente raggiunge
le fonti in HTTPS ma non FMA (solo HTTP, e la copia su web.archive.org è bloccata):
la pipeline completa non gira qui.
- Verificati sui file veri: 05 (ingestione completa); 06 su un banco di prova con
  malattie reali e strutture BodyParts3D legate a UBERON (senza FMA): 8.978 legami
  documento → malattia, controllati a campione; la ricerca vettoriale su un indice
  parziale (vedi "Ricerca" sotto).
- **Non** verificati: tutto ciò che dipende da FMA (03, 04, ereditarietà, tessuti,
  nomi italiani) e il criterio "ogni struttura addominale con `uberon_id` ha ≥ 1
  documento", che richiede le regioni.

**Misurato sui dati reali (computer con RTX 5060, 14/11/2026)**: pipeline completa;
119 test passati, 2 falliti:
- **Fase 3 chiusa dall'utente il 14/11/2026** con l'ultima misura: 121 test passati,
  ricerca ≥ 18/20 (fusione per posizione), 19 strutture addominali senza documenti
  **accettate come lacune** (test: non devono aumentare).
- strutture addominali con `uberon_id` senza documenti: 78 → 25 (legami 'container').
  Con le varianti di nome per parentesi e plurale latino (dopo quella misura) il banco
  di prova qui scende da 27 a 21. Le rimaste sono quasi tutte strutture di cui il corpus
  non ha un capitolo (arteria gastroduodenale, vene frenica e testicolare, perineo) con
  contenitori troppo larghi in BodyParts3D: il criterio "zero" probabilmente non si
  raggiunge con le sole relazioni dichiarate. **Decisione dell'utente**: accettare le
  lacune dichiarate, o aspettare Europe PMC (Fase 6) per coprirle.
- ricerca, 20 domande (soglia 18): 16/20 con i soli paragrafi; 17/20 con titoli e
  paragrafi uniti per distanza (i titoli dominavano: le distanze non sono
  confrontabili). Ora le liste si fondono per posizione (Reciprocal Rank Fusion):
  **da misurare** con `pytest -q -s tests/test_search_quality.py`. "Ittero nel neonato"
  è sbagliata da tutte le varianti provate.
- muscoli in scena 47 (BodyParts3D ne ha pochi): soglia del test corretta.

**Fase 4 (assistente) rinviata per decisione dell'utente** (14/11/2026): niente
`POST /ask`, niente modello di linguaggio. Le Fasi 5 e 6 sono fatte senza di esso:

- **Fase 5 — dal sintomo al corpo** (`POST /locate`, casella "Dal sintomo al corpo"
  nel pannello). 04 calcola `phenotype_locus` (`pipeline/lib/phenosite.py`): sede HPO
  dichiarata, o ereditata dall'antenato is_a più vicino (molti sintomi comuni non ne
  hanno una propria), poi la struttura in scena o il "tutto" più vicino. 07 indicizza
  un vettore per nome e sinonimo di fenotipo con `LOCATE_MODEL` =
  `multilingual-e5-large` (prefisso "query:" da entrambe le parti). Frasi di prova in
  `tests/fixtures/symptoms.json`, scritte prima del codice (commit separato).
  Misurato qui (banco di prova): e5-base 12 → 15/20, e5-large **19/20** (soglia 16).
  I nomi italiani del progetto di traduzione HPO, provati, peggiorano (13/20): non
  usati. Milza e tiroide mancano da BodyParts3D.
- **Fase 6 — Europe PMC**, adattata: senza assistente, voce "Letteratura" nella
  scheda (`GET /structure/{id}/literature`): articoli open access cercati in tempo
  reale per nome della struttura, mai ingeriti, ognuno con la sua licenza e il link a
  Europe PMC (DOI a parte). La scheda ci si apre quando non ha contenuti locali: le 19
  lacune della Fase 3 ricevono articoli. Provato dal vivo; i link non si aprono da
  questo ambiente (403 ai client automatici): **da verificare nel browser**.

## Da fare per primo, sul tuo computer

Dopo le Fasi 5 e 6 (Prompt dei comandi, nella cartella del progetto):

```bash
git pull
npm run pipeline:ontologies   # 03: ora salva i sinonimi dei fenotipi
npm run pipeline:bridge       # 04: calcola fenotipo → struttura (phenotype_locus)
npm run pipeline:links        # 06: registra Europe PMC tra le fonti
npm run pipeline:embed        # 07: solo i vettori dei fenotipi (scarica e5-large, ~2 GB)
set PYTHONUTF8=1
.venv\Scripts\pytest -q
```

Poi:
- `pytest -q -s tests/test_locate_quality.py`: i 20 sintomi, ≥ 16 giusti.
- nell'app: la casella "Dal sintomo al corpo"; la voce "Letteratura" di una scheda
  (aprire qualche link: da qui non si è potuto verificare che si aprano).
- **verifica della Fase 2**: `http://localhost:5173/?perf` (caricamento < 3 s, ~60 fps).

## Problemi aperti, in ordine di valore

1. **Copertura clinica**: da misurare con `fma_is_a` (vedi `coverage.md`).
2. **Legami documento → struttura** deboli dove la struttura non ha un termine UBERON
   proprio: arrivano dalla sede delle malattie e dai capitoli di anatomia. Vedi
   `documents.md`.
3. **Polmoni senza superficie** in BodyParts3D 4.0 (solo vie bronchiali e vasi).
4. **Validazione clinica**: serve una persona con formazione medica prima di rendere
   pubblica l'app (SPEC §13). Il repository deve restare **privato**.
5. **StatPearls è CC BY-NC-ND 4.0**: uso non commerciale, testo non modificato. Va
   ricordato prima di qualunque uso pubblico o commerciale.

## Come rimettere in piedi l'ambiente

Su un computer nuovo (Windows; `make` non serve):

```bash
python -m venv .venv
.venv/Scripts/pip install -e ".[dev,embed]"
npm install
npm --prefix web install
npm run pipeline        # scarica ~2,7 GB e produce data/atlas.db + data/meshes/*.glb
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
- **Ogni documento ha una licenza accertata** (I3); StatPearls solo dall'FTP NCBI.
- Nessuna parola come "diagnosi" o "probabilmente hai" nell'interfaccia (SPEC §9).
- Commit convenzionali con scope = fase. Dopo il pipeline, leggere `data/reports/`.
- Su Windows: eseguire Python con `PYTHONUTF8=1`; nel bash di Git gli heredoc con `'''`
  si rompono (scrivere i file con l'editor); l'API parte senza `--reload`
  (`npm run dev:api:reload` solo in un terminale separato).
- In un ambiente cloud che lascia passare solo HTTPS: i purl OBO sono già in https;
  FMA no (vedi sopra).
- Più dettagli e scelte documentate: `README.md`, `SPEC.md`.

## Prossimo passo suggerito

Verificare sul computer le Fasi 5 e 6 (sopra) e la misura di Fase 2. Poi, quando
l'utente lo decide, la Fase 4 (assistente con citazioni): `POST /ask` con
`enforce_citations` e la sua suite di test, `ChatPanel`, prompt di sistema con il
rifiuto di SPEC §9; serve scegliere il modello di linguaggio (locale o via API).
