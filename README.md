# ATLAS

**Un atlante anatomico 3D del corpo umano che sa anche di clinica.** Si gira il corpo
intero nel browser, si clicca un organo e la scheda dice quali malattie lo colpiscono,
quali segni le accompagnano e dove leggerne di più. Oppure si parte dall'altra parte:
si scrive un sintomo ("mi fa male la pancia a destra") e il corpo si illumina dove
quel sintomo ha sede.

Ogni informazione clinica rimanda alla sua fonte pubblica. Niente è inventato, niente
è scritto a mano, niente è generato da un modello linguistico.

> [!WARNING]
> **ATLAS è uno strumento di studio, non un dispositivo medico.** Non serve a fare
> diagnosi, non sostituisce un medico e i suoi contenuti non sono stati validati da
> personale sanitario. In caso di sintomi reali rivolgiti a un professionista.

---

## Cosa fa

| | |
|---|---|
| **Corpo intero in 3D** | Sei regioni (testa, collo, torace, addome con pelvi, arti superiori e inferiori), **838 strutture** dai modelli di BodyParts3D. Rotazione, zoom, volo della camera sulla struttura scelta, "mostra solo questo". |
| **Strati** | Pelle → Muscoli → Ossa → Organi: toglie ciò che sta sopra e vela ciò che sta sotto, come sfogliare una tavola anatomica. |
| **Scheda clinica** | Per ogni struttura: patologie (MONDO, con codice ICD-11 quando esiste) e segni (HPO), ognuno con il rimando alla fonte e alla relazione che lo lega all'organo. |
| **Letture** | Capitoli di StatPearls, schede di MedlinePlus e Orphanet collegati alla struttura: **16.573 documenti**, ciascuno con la sua licenza. |
| **Ricerca nei testi** | Domande in italiano su 140.000 paragrafi, con ricerca semantica locale (nessun servizio esterno). |
| **Dal sintomo al corpo** | Si descrive un sintomo a parole proprie; ATLAS trova i fenotipi HPO più vicini e illumina le strutture in cui hanno sede. Il testo scritto non viene salvato. |
| **Letteratura** | Articoli open access da Europe PMC, cercati in tempo reale per nome della struttura. |

## Come è fatto

```
 fonti pubbliche ──► pipeline Python (01–07) ──► SQLite + sqlite-vec ──► API FastAPI ──► React + three.js
  (ontologie,         scarica, collega,           atlas.db               sola lettura      scena 3D,
   modelli 3D,        indicizza; nessun ID        meshes/*.glb                             schede, ricerca
   testi clinici)     inventato
```

- **Pipeline** (`pipeline/`): sette passi idempotenti che scaricano le fonti con la
  loro firma SHA-256, convertono i modelli 3D in GLB compressi, caricano le ontologie,
  fanno il ponte tra le anatomie (FMA ↔ UBERON), leggono i testi clinici, li collegano
  alle strutture e calcolano gli embedding in locale.
- **API** (`api/`): FastAPI in sola lettura sul database prodotto dalla pipeline.
- **Web** (`web/`): React, React Three Fiber, Zustand, Tailwind.
- **Ricerca**: `intfloat/multilingual-e5` in locale, `sqlite-vec` per i vettori,
  fusione per posizione (Reciprocal Rank Fusion) tra titoli e paragrafi.

### Le regole che il progetto non viola

Sono scritte in [SPEC.md](SPEC.md) e controllate dai test:

1. **Ogni affermazione clinica cita la sua fonte.**
2. **Ogni documento porta la sua licenza**, verificata uno per uno.
3. **Nessun identificativo è costruito a mano**: un legame esiste solo se una fonte lo
   dichiara; ciò che non si trova finisce in una tabella di "non mappati" e in un report.
4. **Nessun dato di pazienti**, mai.

Le scelte tecniche, con il loro perché e i numeri misurati, sono in
[docs/SCELTE.md](docs/SCELTE.md).

## Fonti e licenze

| Fonte | Cosa fornisce | Licenza |
|---|---|---|
| [BodyParts3D](https://lifesciencedb.jp/bp3d/) | Modelli 3D delle strutture | CC BY 4.0 |
| [FMA](https://sig.biostr.washington.edu/projects/fm/) | Ontologia anatomica di riferimento | CC BY 4.0 |
| [UBERON](https://obophenotype.github.io/uberon/) | Ponte tra anatomia e clinica | CC BY 3.0 |
| [HPO](https://hpo.jax.org/) e annotazioni HPOA | Segni e sintomi, sede dei fenotipi | Licenza HPO (uso libero con attribuzione) |
| [MONDO](https://mondo.monarchinitiative.org/) | Malattie | CC BY 4.0 |
| [Disease Ontology](https://disease-ontology.org/) | Sede delle malattie | CC0 |
| [ICD-11](https://icd.who.int/) | Codici delle malattie | CC BY-ND 3.0 IGO |
| [Wikidata](https://www.wikidata.org/) | Nomi italiani delle strutture | CC0 |
| [MedlinePlus](https://medlineplus.gov/) | Schede divulgative | Pubblico dominio |
| [Orphanet](https://www.orpha.net/) | Malattie rare | CC BY 4.0 |
| [StatPearls](https://www.ncbi.nlm.nih.gov/books/NBK430685/) | Capitoli clinici e di anatomia | CC BY-NC-ND 4.0 (per capitolo) |
| [Europe PMC](https://europepmc.org/) | Letteratura, in tempo reale | Quella del singolo articolo |

Nessun dato di terzi è incluso in questo repository: la pipeline li scarica dalle
fonti ufficiali e li tiene in `data/`, che non viene versionata.

## Provarlo

Servono **Python 3.11+**, **Node 20+** e qualche GB libero per le fonti scaricate. Una GPU NVIDIA non è
necessaria, ma riduce il calcolo degli embedding da ore a minuti.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev,embed]"        # Windows: .venv\Scripts\pip
npm install
npm --prefix web install
```

Per usare la GPU, installare PyTorch con CUDA **prima** della riga `pip install`
(<https://pytorch.org/get-started/locally/>; le schede RTX 50 richiedono CUDA 12.8+).

Poi si costruisce il database (una volta sola, poi ogni passo salta ciò che ha già
fatto) e si avvia l'applicazione:

```bash
npm run pipeline
```

```bash
npm run dev
```

L'atlante è su <http://localhost:5173>, l'API su <http://localhost:8000/docs>.

| Passo | Cosa fa |
|---|---|
| `pipeline:fetch` | Scarica le fonti in `data/raw/` con URL, data e SHA-256 in `MANIFEST.json` |
| `pipeline:meshes` | Modelli OBJ → GLB compressi (Draco), uno per regione |
| `pipeline:ontologies` | FMA, HPO, MONDO, Disease Ontology, ICD-11, Wikidata → tabelle |
| `pipeline:bridge` | Ponte FMA ↔ UBERON, ereditarietà destra/sinistra, report di copertura |
| `pipeline:documents` | MedlinePlus, Orphanet, StatPearls, con licenza per documento |
| `pipeline:links` | Documento → malattia → struttura, solo da riferimenti dichiarati |
| `pipeline:embed` | Paragrafi, titoli e fenotipi → vettori in `sqlite-vec` |

Dopo ogni esecuzione i report in `data/reports/` dicono cosa è stato collegato e cosa
no. Variabili opzionali: `ATLAS_DB`, `ATLAS_MESHES`, `ATLAS_CORS_ORIGINS`,
`ATLAS_API_KEY` (API) con `VITE_ATLAS_API_KEY` (web). Note per Windows in
[docs/SCELTE.md](docs/SCELTE.md#note-per-chi-sviluppa-su-windows).

## Qualità

```bash
.venv/bin/ruff check api pipeline tests && .venv/bin/mypy api pipeline && .venv/bin/pytest
```

```bash
npm --prefix web run typecheck && npm --prefix web run lint && npm --prefix web test
```

Sui dati reali: **135 test passati**, inclusi i criteri di accettazione di ogni fase,
misurati su domande scritte prima del codice:

- **Ricerca nei testi:** almeno 18 domande su 20 trovano il documento giusto nei primi 5.
- **Dal sintomo al corpo:** 19 sintomi su 20, scritti in italiano colloquiale, portano
  alla struttura attesa.

## Limiti

- **Nessuna validazione clinica.** I contenuti vengono da fonti autorevoli, ma nessun
  medico ha controllato come sono stati collegati.
- **Anatomia incompleta.** BodyParts3D non ha la superficie dei polmoni, né milza e
  tiroide, e ha pochi muscoli scheletrici. Alcune strutture (piccoli vasi, perineo)
  non hanno documenti dedicati: lì aiuta la voce "Letteratura".
- **Testi in inglese.** Le fonti cliniche sono in inglese; l'interfaccia, i nomi delle
  strutture (dove esistono) e le domande sono in italiano.
- **Nessun assistente conversazionale.** Previsto nella SPEC (Fase 4), non realizzato:
  ATLAS non usa modelli linguistici generativi.

## Perché esiste

È un progetto personale, nato per vedere fin dove si arriva collegando con rigore
dati pubblici di anatomia e clinica, senza inventare nulla. Può servire:

- **a chi studia medicina o anatomia**, per passare dalla forma di un organo alla sua
  patologia e alle letture giuste;
- **a chi lavora su ontologie biomediche**, come esempio concreto di ponte FMA ↔
  UBERON ↔ HPO ↔ MONDO, con tutte le lacune documentate;
- **come base per una collaborazione** (didattica, universitaria o di ricerca), a
  partire da una validazione clinica dei contenuti.

## Contatti

**Se il progetto ti interessa, per studio, collaborazione o qualunque altra idea,
scrivimi.** Puoi aprire una [issue](https://github.com/CerryWhy/Atlas/issues) o
contattarmi dal mio profilo GitHub, [@CerryWhy](https://github.com/CerryWhy).

## Licenza

Il codice è pubblicato per essere letto e studiato; per riusarlo, scrivimi. I dati
restano soggetti alle licenze delle rispettive fonti, elencate sopra.
