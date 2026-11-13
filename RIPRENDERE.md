# Come riprendere il lavoro su ATLAS

Per un agente di coding (o per te) che apre una nuova sessione. Leggi prima `SPEC.md`:
contiene gli invarianti non negoziabili. Questo file dice a che punto siamo.

## Stato (13 novembre 2026, notte)

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

**Ricerca (accettazione Fase 3, 20 domande in `tests/fixtures/search_queries.json`,
soglia ≥ 18 nei primi 5)**: qui, con il modello piccolo (`multilingual-e5-small`) su
CPU e indicizzando solo il primo chunk di ogni documento (`--first-chunks 1`, 17.507
vettori su ~140.000), **17/20: il test non passa per una domanda**. Mancate:
- "calcoli della colecisti e colica biliare": trova "Choledocholithiasis" (pertinente,
  ma non tra i titoli attesi);
- "milza ingrossata, splenomegalia" e "ittero nel neonato": risposte sbagliate.
Le domande e i titoli attesi NON vanno ritoccati dopo aver visto i risultati. La misura
che conta è quella con l'indice completo e `multilingual-e5-base` (la configurazione
predefinita), da fare sul computer con GPU. Se resta sotto 18, migliorare il recupero
(es. sinonimi italiani → inglesi nella domanda, o un riordino dei risultati), non il test.

Non fatto: Fasi 4–6 della SPEC (assistente con citazioni, sintomo → corpo, Europe PMC).

## Da fare per primo, sul tuo computer

```bash
git fetch origin && git checkout claude/funny-franklin-2ikacr
# con GPU NVIDIA: prima torch con CUDA, https://pytorch.org/get-started/locally/
.venv/Scripts/pip install -e ".[dev,embed]"
npm run pipeline        # 01–07; 07 calcola ~140.000 embedding (minuti su GPU)
PYTHONUTF8=1 .venv/Scripts/pytest -q    # i test sui dati non devono essere saltati
```

Poi leggere:
- `data/reports/documents.md`: in fondo, le strutture addominali con `uberon_id` senza
  documenti. Il criterio della Fase 3 ne chiede zero.
- `pytest -q tests/test_search_quality.py -s`: le 20 domande di prova, ≥ 18 giuste.
- `data/reports/is_a_links.md`: la tabella "Antenati usati". Se compaiono antenati
  troppo generici ("Organ", "Muscle organ", "Artery"), abbassare `ISA_MAX_DESCENDANTS`
  (ora 300) o `ISA_MAX_HOPS` (ora 3) in `pipeline/lib/config.py`.
- `data/reports/coverage.md`: quanto rendono le ereditarietà ("+ lato", "+ classe").
- output di 03 (nomi italiani da Wikidata) e di 04 (tessuti; avvisi "classe FMA per i
  tessuti non trovata": correggere il nome in `TISSUE_CLASSES`).
- **verifica della Fase 2**: `http://localhost:5173/?perf`, ruotare e ingrandire per
  qualche secondo (obiettivi: caricamento < 3 s, ~60 fps); provare strati e `flyTo`.
- alcune schede: un osso con lato (nota "classe più generale", nome italiano), il
  fegato (voce "Letture").

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

Eseguire la pipeline completa e verificare i criteri della Fase 3 (sopra). Poi Fase 4:
`POST /ask` con `enforce_citations` e la sua suite di test, `ChatPanel` +
`CitationList`, prompt di sistema con il rifiuto di SPEC §9. Serve decidere quale
modello di linguaggio usa l'assistente (locale o via API, e con quale chiave): è una
scelta dell'utente.
