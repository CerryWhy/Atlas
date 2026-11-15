# ATLAS — Atlante anatomico 3D con ragionamento clinico assistito

> **Documento di specifica e roadmap.**
> Questo file è il brief del progetto. Va tenuto nella root del repo e letto
> integralmente da qualunque agente di coding prima di scrivere codice.
> Se una richiesta dell'utente contraddice gli **Invarianti** (§2) o i
> **Non-obiettivi** (§3), l'agente deve segnalarlo invece di eseguire.

---

## 1. Obiettivo

Costruire un atlante anatomico tridimensionale navigabile in cui ogni struttura
del corpo umano è un nodo collegato al sapere clinico su quella struttura, con
un assistente conversazionale affiancato che sa muovere la vista.

I due percorsi d'uso che definiscono il prodotto:

1. **Esplorazione** — l'utente clicca o cerca una struttura, e ottiene anatomia,
   fisiopatologia, patologie associate e letteratura, tutto citato.
2. **Localizzazione** — l'utente descrive un sintomo in linguaggio naturale, il
   sistema lo mappa a un fenotipo, risale alle strutture coinvolte, **porta la
   camera lì** e apre il quadro delle patologie che lo spiegano.

Il modello mentale è quello della medicina interna: dal segno alla sede, dalla
sede al meccanismo, dal meccanismo allo spazio delle possibilità. Lo strumento
insegna il ragionamento clinico, **non lo sostituisce**.

### Criterio di successo del progetto

Uno studente di medicina al terzo anno lo usa al posto dell'atlante cartaceo
perché è più veloce a rispondere a "perché questo sintomo nasce qui".

---

## 2. Invarianti — non negoziabili

Queste regole non si discutono e non si aggirano. Ogni PR che le viola va
rifiutata.

### I1 — L'ID anatomico è la chiave primaria del sistema

`fma_id` (es. `FMA:7197`) è l'unica chiave che unisce geometria, ontologia e
contenuto. Nessuna tabella, nessun componente e nessuna risposta dell'API
identifica una struttura con una stringa libera. Il nome del nodo dentro ogni
file `.glb` **è** l'FMA ID.

### I2 — Nessuna affermazione senza fonte

Ogni frase che afferma un fatto clinico, in qualunque superficie
dell'applicazione, porta un riferimento a un documento apribile. Le frasi non
coperte da una fonte vengono marcate come non verificate e rese visivamente
distinte. Non esiste un percorso di codice che emetta testo clinico privo di
provenienza.

### I3 — Ogni documento conosce la propria licenza

`document.license` è `NOT NULL`. Un documento senza licenza accertata non entra
nel database. Nessuna eccezione "lo sistemo dopo".

### I4 — Il sistema non conosce pazienti

Nessun input riferito a una persona specifica, nessuna anamnesi, nessun dato
individuale persistito, nessun output nella forma "tu potresti avere X".
Il sistema ragiona su malattie in astratto. Questo è ciò che tiene il prodotto
fuori dal perimetro del dispositivo medico (vedi §9).

### I5 — Nessun identificatore inventato

FMA, UBERON, HPO, MONDO e ICD-11 sono ID reali che provengono da file scaricati.
Un agente che non trova un ID lo segnala come mancante. Non lo deduce, non lo
costruisce per analogia, non lo plausibilizza.

### I6 — La pipeline è separata dall'applicazione

`pipeline/` produce `data/atlas.db` e `data/meshes/*.glb`. L'applicazione legge
quei due artefatti e non sa nulla di ontologie, parser OBO o file OBJ. Si deve
poter ricostruire tutta la conoscenza da zero senza toccare una riga di
frontend.

---

## 3. Non-obiettivi

Cose che il progetto **non** fa, elencate perché sono tentazioni ricorrenti.

- **Non è un symptom checker.** Non prende sintomi di una persona e non
  restituisce cosa ha.
- **Non ingerisce "tutta la medicina".** Il corpus locale è piccolo e curato;
  la profondità arriva dalla struttura del grafo e dal recupero live (§6).
- **Non usa i mesh di Z-Anatomy.** Sono CC BY-SA 4.0, cioè copyleft: userebbero
  l'intero progetto. Si usa **solo BodyParts3D** (CC BY 4.0).
- **Non usa SNOMED CT.** È gratuito solo nei paesi membri; altrove le tariffe
  sono proibitive e l'Italia compare nella tabella dei territori a pagamento.
  Si usa ICD-11 (CC BY-ND 3.0 IGO, API gratuita) + MONDO/DO.
- **Non scarica in blocco da NCBI fuori dall'FTP ufficiale.** Il recupero
  sistematico tramite qualunque altro processo automatico è vietato dai termini,
  anche per i contenuti open access.
- **Non costruisce il corpo intero prima che l'addome funzioni.**
- **Non introduce Neo4j, Docker Compose, Kubernetes o un ORM** finché non c'è un
  problema reale che li richieda.

---

## 4. Stack

| Strato | Tecnologia | Vincolo |
|---|---|---|
| Rendering | three.js via `@react-three/fiber` + `@react-three/drei` | Niente three.js imperativo nei componenti |
| UI | React 18 + TypeScript (`strict: true`) + Tailwind | |
| Stato | Zustand | Un solo store, `useAtlasStore` |
| Build | Vite | |
| Backend | FastAPI + Uvicorn | Sottile: API key, CORS, query. Niente logica di dominio |
| Dati | SQLite + `sqlite-vec` | Un file. Niente ORM: SQL esplicito in `queries.py` |
| Embedding | `sentence-transformers`, modello multilingue, in locale su GPU | Nessun testo esce per gli embedding |
| Mesh | glTF 2.0 binario (`.glb`) con compressione Draco | Un GLB per regione anatomica |
| Pipeline | Python 3.11+, script numerati, idempotenti | Ogni script è rieseguibile senza effetti collaterali |

Qualità: `ruff` + `mypy` lato Python, `eslint` + `tsc --noEmit` lato web.
Test con `pytest` e `vitest`.

---

## 5. Struttura del repository

```
atlas/
├── SPEC.md                      # questo file
├── README.md                    # come far partire le cose
│
├── pipeline/                    # ETL offline → data/atlas.db + data/meshes/
│   ├── 00_config.py             # percorsi, costanti, la regione attiva
│   ├── 01_fetch_sources.py      # scarica BodyParts3D + file ontologie
│   ├── 02_build_meshes.py       # OBJ → GLB, Draco, centroidi, bbox
│   ├── 03_load_ontologies.py    # OBO/OWL → tabelle structure/phenotype/disease
│   ├── 04_bridge_fma_uberon.py  # crosswalk + report delle strutture non mappate
│   ├── 05_ingest_documents.py   # corpus testuale, con licenza obbligatoria
│   ├── 06_link_documents.py     # documento → fma_id / mondo_id
│   ├── 07_embed.py              # chunking + embedding locali
│   └── lib/{obo.py,mesh.py,db.py}
│
├── api/
│   ├── main.py
│   ├── db.py                    # connessione, caricamento estensione sqlite-vec
│   ├── queries.py               # TUTTO l'SQL vive qui, nient'altro
│   ├── routes/
│   │   ├── structure.py         # GET /structure/{fma_id}
│   │   ├── locate.py            # POST /locate      (sintomo → corpo)
│   │   └── ask.py               # POST /ask         (domanda → risposta citata)
│   ├── retrieval/
│   │   ├── local.py             # tier 1: corpus curato
│   │   ├── europepmc.py         # tier 2: letteratura live
│   │   └── fusion.py            # ranking e soglia di confidenza
│   └── llm/
│       ├── synthesize.py
│       └── citations.py         # enforce_citations() — vedi I2
│
├── web/src/
│   ├── scene/
│   │   ├── Atlas.tsx            # <Canvas>, luci, controlli
│   │   ├── Region.tsx           # carica un GLB, mappa nodi → fma_id
│   │   ├── Structure.tsx        # una mesh: hover / select / highlight
│   │   └── CameraRig.tsx        # flyTo(target) con easing
│   ├── panels/
│   │   ├── StructurePanel.tsx   # cosa hai selezionato
│   │   ├── ChatPanel.tsx        # l'assistente
│   │   ├── CitationList.tsx
│   │   └── LayerControls.tsx    # pelle → muscoli → organi
│   ├── store/atlas.ts
│   ├── api/client.ts
│   └── types/atlas.d.ts         # tipi condivisi, generati dallo schema OpenAPI
│
├── data/
│   ├── raw/                     # .gitignore — materiale scaricato
│   ├── atlas.db                 # .gitignore — l'artefatto della pipeline
│   └── meshes/*.glb             # .gitignore
│
└── tests/
```

---

## 6. Modello dei dati

Schema di riferimento. Le migrazioni vivono in `pipeline/lib/db.py`.

```sql
-- ─── ANCORA ────────────────────────────────────────────────────────────────
-- Un record per concetto anatomico. È la chiave di volta dell'intero sistema.
CREATE TABLE structure (
  fma_id        TEXT PRIMARY KEY,            -- 'FMA:7197'
  label_en      TEXT NOT NULL,
  label_la      TEXT,                        -- Terminologia Anatomica
  label_it      TEXT,
  uberon_id     TEXT,                        -- ponte verso i fenotipi
  parent_fma_id TEXT REFERENCES structure(fma_id),   -- gerarchia part_of
  system        TEXT,                        -- 'digestive' | 'nervous' | ...
  region        TEXT,                        -- 'abdomen' | 'thorax' | ...
  depth         INTEGER NOT NULL DEFAULT 0,  -- livello nell'albero
  -- geometria
  mesh_file     TEXT,                        -- 'abdomen.glb'
  mesh_node     TEXT,                        -- nome del nodo nel GLB (= fma_id)
  cx REAL, cy REAL, cz REAL,                 -- centroide → bersaglio camera
  radius        REAL                         -- raggio bbox → distanza di zoom
);
CREATE INDEX idx_structure_parent ON structure(parent_fma_id);
CREATE INDEX idx_structure_uberon ON structure(uberon_id);
CREATE INDEX idx_structure_region ON structure(region);

-- ─── ONTOLOGIA CLINICA ─────────────────────────────────────────────────────
CREATE TABLE phenotype (
  hpo_id     TEXT PRIMARY KEY,               -- 'HP:0000952'
  label      TEXT NOT NULL,
  definition TEXT
);

CREATE TABLE disease (
  mondo_id   TEXT PRIMARY KEY,               -- 'MONDO:0005359'
  label      TEXT NOT NULL,
  icd11_code TEXT,
  definition TEXT
);

-- fenotipo → sede anatomica (dalle definizioni logiche di HPO)
CREATE TABLE phenotype_structure (
  hpo_id    TEXT NOT NULL REFERENCES phenotype(hpo_id),
  uberon_id TEXT NOT NULL,
  PRIMARY KEY (hpo_id, uberon_id)
);

-- malattia → fenotipi (da HPOA; frequency è il campo HPO, può essere NULL)
CREATE TABLE disease_phenotype (
  mondo_id  TEXT NOT NULL REFERENCES disease(mondo_id),
  hpo_id    TEXT NOT NULL REFERENCES phenotype(hpo_id),
  frequency TEXT,
  PRIMARY KEY (mondo_id, hpo_id)
);

-- malattia → sede anatomica (dagli assiomi di Disease Ontology)
CREATE TABLE disease_structure (
  mondo_id  TEXT NOT NULL REFERENCES disease(mondo_id),
  uberon_id TEXT NOT NULL,
  PRIMARY KEY (mondo_id, uberon_id)
);

-- ─── CONTENUTO ─────────────────────────────────────────────────────────────
CREATE TABLE document (
  doc_id     TEXT PRIMARY KEY,
  source     TEXT NOT NULL,                  -- 'statpearls' | 'medlineplus' | ...
  title      TEXT NOT NULL,
  url        TEXT NOT NULL,
  license    TEXT NOT NULL,                  -- ⚠️ INVARIANTE I3
  retrieved  TEXT NOT NULL,                  -- ISO date
  text       TEXT NOT NULL
);

CREATE TABLE document_structure (
  doc_id    TEXT NOT NULL REFERENCES document(doc_id),
  fma_id    TEXT NOT NULL REFERENCES structure(fma_id),
  relevance REAL NOT NULL DEFAULT 1.0,
  PRIMARY KEY (doc_id, fma_id)
);

CREATE TABLE document_disease (
  doc_id   TEXT NOT NULL REFERENCES document(doc_id),
  mondo_id TEXT NOT NULL REFERENCES disease(mondo_id),
  PRIMARY KEY (doc_id, mondo_id)
);

CREATE TABLE chunk (
  chunk_id  TEXT PRIMARY KEY,
  doc_id    TEXT NOT NULL REFERENCES document(doc_id),
  ordinal   INTEGER NOT NULL,
  text      TEXT NOT NULL
);
-- embedding in tabella virtuale sqlite-vec, chiave = chunk_id

-- ─── DIAGNOSTICA DELLA PIPELINE ────────────────────────────────────────────
-- Non è scaffolding: è il cruscotto che dice quanta parte del corpo è "muta".
CREATE TABLE unmapped (
  kind    TEXT NOT NULL,        -- 'fma_no_uberon' | 'mesh_no_concept' | ...
  ref_id  TEXT NOT NULL,
  label   TEXT,
  note    TEXT
);
```

### La query che fa la profondità verticale

La sensazione di "si può scendere all'infinito" è questa ricorsione, non la
dimensione del corpus:

```sql
WITH RECURSIVE descend(fma_id, label_en, depth) AS (
  SELECT fma_id, label_en, 0 FROM structure WHERE fma_id = :root
  UNION ALL
  SELECT s.fma_id, s.label_en, d.depth + 1
  FROM structure s JOIN descend d ON s.parent_fma_id = d.fma_id
  WHERE d.depth < 8
)
SELECT * FROM descend ORDER BY depth;
```

---

## 7. Fonti dei dati

| Fonte | Cosa dà | Licenza | Nota operativa |
|---|---|---|---|
| **BodyParts3D** (DBCLS) | Mesh OBJ etichettati con ID FMA | CC BY 4.0 (versione LATEST) | Unica fonte di geometria. Attribuzione obbligatoria in app |
| **FMA** (Univ. of Washington) | Ontologia anatomica, gerarchia `part_of` | Open | Definisce `parent_fma_id` |
| **UBERON** | Anatomia cross-specie, xref verso FMA | CC BY 3.0 | È il ponte verso HPO/DO |
| **HPO** | ~13.000 fenotipi, definizioni logiche su UBERON | Vedi licenza HPO | Il motore di "sintomo → sede" |
| **HPOA** | Annotazioni malattia ↔ fenotipo | Come HPO | Porta il campo `frequency` |
| **MONDO** | Ontologia di malattie unificata | CC BY 4.0 | Chiave primaria delle malattie |
| **Disease Ontology** | Assiomi malattia → sede, sintomi | CC0 | Importa ~800 termini UBERON e ~894 sintomi |
| **ICD-11** (WHO) | Codici diagnostici, API REST, deploy locale | CC BY-ND 3.0 IGO | `-ND`: si può incorporare, **non modificare** |
| **StatPearls** (NCBI Bookshelf) | Articoli clinici peer-reviewed | Variabile per opera | **Solo FTP ufficiale**; leggere la licenza file per file |
| **MedlinePlus** (NLM) | Divulgazione clinica | Pubblico dominio US | Livello introduttivo |
| **Orphanet** | Malattie rare | CC BY 4.0 | |
| **Europe PMC** | ~43M pubblicazioni, >5M full-text, >2,5M riutilizzabili per text mining | Per articolo | **Tier 2, live, non ingerito.** API REST senza chiave |

### Attribuzioni obbligatorie in applicazione

Una pagina `/attribution` raggiungibile dal footer, che riporta almeno:

> BodyParts3D, © The Database Center for Life Science, licensed under
> CC Attribution 4.0 International.

più la riga di attribuzione di ogni altra fonte effettivamente usata.

---

## 8. Architettura del recupero — tre livelli

Il corpus locale non serve a rendere il modello più intelligente: i modelli di
frontiera già superano i sistemi clinici specializzati sui benchmark medici.
Serve a rendere le affermazioni **verificabili**. Progettare di conseguenza.

```
Tier 1  corpus curato locale      decine di migliaia di documenti, indicizzati
        ↓ (se confidenza bassa)
Tier 2  Europe PMC live           l'intera letteratura, su richiesta, non ingerita
        ↓
Tier 3  sintesi del modello       obbligata a citare Tier 1 e 2
```

```python
async def ask(question: str, focus_fma: str | None = None) -> Answer:
    hits = local_search(question, focus_fma)
    if mean_score(hits) < CONFIDENCE_THRESHOLD or len(hits) < MIN_HITS:
        hits += await europepmc.search(question, open_access_only=True)
    draft = await llm.synthesize(question, sources=hits)
    return enforce_citations(draft, hits)      # INVARIANTE I2
```

`enforce_citations` è una funzione reale con test propri: le fonti entrano
numerate, il modello deve emettere marcatori `[n]`, un passaggio finale verifica
che ogni frase assertiva ne porti uno e marca le altre come non verificate.

### La risposta è strutturata, non testo

```ts
type Answer = {
  markdown:   string
  citations:  Citation[]
  structures: FmaId[]     // il frontend le illumina e ci porta la camera
  diseases:   MondoId[]
}
```

È questo che fonde chat e scena 3D in un unico strumento invece di due pannelli
affiancati. L'assistente non *dice* "fegato": restituisce `FMA:7197` e il fegato
si accende.

---

## 9. Perimetro legale

Il software fornisce informazioni di carattere anatomico e fisiopatologico a
scopo di studio. **Non** è destinato a diagnosi, prevenzione, monitoraggio,
predizione, prognosi o trattamento di una malattia in una persona determinata.

Questo confine non è cosmetico: sotto il regolamento MDR (UE 2017/745) la
qualificazione di un software come dispositivo medico dipende dalla
**destinazione d'uso dichiarata**, e la Regola 11 dell'Allegato VIII classifica
almeno in classe IIa il software destinato a fornire informazioni usate per
decisioni diagnostiche o terapeutiche — senza richiedere che il software esegua
la diagnosi.

Conseguenze operative vincolanti:

- Nessuna copy di marketing, nessun testo in-app e nessun prompt di sistema
  usa le parole "diagnosi", "ti consiglio", "probabilmente hai".
- Nessun campo di input accetta dati clinici individuali.
- Nessuna persistenza di dati riferibili a una persona.
- Disclaimer permanente e non chiudibile nel pannello dell'assistente.
- Il prompt di sistema dell'LLM contiene il rifiuto esplicito: se l'utente
  descrive la propria situazione clinica, l'assistente risponde spiegando il
  meccanismo in generale e rimanda a un medico, senza formulare ipotesi
  personalizzate.

Nota: a dicembre 2025 è stata proposta una revisione della Regola 11 che
riclassificherebbe parte di questo software in classe I. È una proposta, non
diritto vigente: non costruirci sopra alcuna decisione.

---

## 10. Roadmap

Ogni fase ha un criterio di accettazione verificabile. **Una fase non si
considera chiusa finché il criterio non passa.** Non si inizia la fase N+1 con
la N aperta.

### Fase 0 — Proiettile tracciante
*Obiettivo: una fetta sottilissima che attraversa tutti gli strati.*

- Scaffolding del repo, `npm run dev` che avvia API e web insieme
- **Un solo** mesh (fegato) esportato a mano in `liver.glb`
- **Una sola** riga in `structure`, scritta a mano
- Tre righe reali in `disease` + `disease_structure`, copiate da MONDO
- `GET /structure/FMA:7197` funzionante
- Scena R3F che carica il GLB, lo rende cliccabile, apre il pannello

**Accettazione:** clicchi il fegato nel browser e vedi una patologia epatica
reale con il suo codice ICD-11, letta da `atlas.db`.

**Perché prima di tutto:** se parti dalla pipeline completa passi tre settimane
su mapping ontologici senza aver mai visto un organo sullo schermo.

---

### Fase 1 — Pipeline ontologica, regione addominale
*Obiettivo: `atlas.db` popolato davvero.*

- `01` scarica BodyParts3D (versione LATEST, CC BY 4.0) e i file ontologici
- `02` filtra le strutture addominali, converte OBJ → GLB con Draco, calcola
  centroidi e raggi di bounding box
- `03` carica FMA (gerarchia `part_of`), UBERON, HPO, HPOA, MONDO, DO
- `04` costruisce il crosswalk FMA ↔ UBERON e **popola `unmapped`**

**Accettazione:**
- `SELECT COUNT(*) FROM structure WHERE region='abdomen'` ≥ 80
- La query ricorsiva su `FMA:7197` restituisce ≥ 5 livelli
- Il report `unmapped` esiste ed è stato letto: si sa quale percentuale di
  strutture addominali non ha un `uberon_id`
- Ogni struttura con mesh ha centroide e raggio non nulli

**Trappola nota:** la copertura degli xref UBERON→FMA non è totale. È il punto
più fastidioso dell'intero progetto. Non nasconderlo: misuralo.

---

### Fase 2 — Scena 3D completa
*Obiettivo: l'addome navigabile.*

- `Region.tsx` carica il GLB e mappa ogni nodo al suo `fma_id`
- Hover con etichetta, click con selezione, outline sulla struttura attiva
- Controlli di strato: pelle → muscoli → organi, con opacità
- `CameraRig.flyTo(fma_id)` con easing, distanza derivata da `radius`
- Isolamento ("mostra solo questo") e briciole di pane gerarchiche

**Accettazione:** ~80 strutture caricate in meno di 3 secondi su connessione
normale, interazione fluida a 60 fps, `flyTo` inquadra correttamente qualunque
struttura senza compenetrazioni.

---

### Fase 3 — Contenuto, livello 1
*Obiettivo: ogni nodo ha qualcosa da dire.*

- `05` ingestione da FTP ufficiale NCBI, con `license` valorizzata per ogni file
- MedlinePlus e Orphanet per i livelli divulgativo e raro
- `06` collegamento documento → `fma_id` / `mondo_id`
- `07` chunking e embedding locali su GPU

**Accettazione:**
- Ogni struttura addominale con `uberon_id` ha ≥ 1 documento collegato
- Zero righe in `document` con `license` vuota o segnaposto
- La ricerca vettoriale su 20 query di prova restituisce chunk pertinenti

---

### Fase 4 — L'assistente con citazioni
*Obiettivo: l'invariante I2 diventa codice.*

- `POST /ask` con i tier 1 e 3
- `enforce_citations` con la propria suite di test
- `ChatPanel` + `CitationList`, click sulla citazione → apre la fonte
- Prompt di sistema con il rifiuto di §9

**Accettazione:**
- Su 30 domande di prova, ogni frase assertiva porta una citazione valida
- Le frasi non coperte sono rese visivamente distinte, non eliminate in silenzio
- Una domanda formulata in prima persona ("ho mal di pancia, cos'ho?") riceve
  una risposta generale sul meccanismo e il rimando al medico

---

### Fase 5 — Sintomo → corpo
*Obiettivo: la funzione che vende il prodotto.*

- `POST /locate`: testo → embedding → fenotipi HPO → UBERON → FMA → centroidi
- Il frontend illumina le strutture e ci porta la camera
- L'`Answer.structures` della chat alimenta lo stesso percorso

**Accettazione:** su 20 sintomi scritti in italiano colloquiale, ≥ 16 portano
alla struttura corretta. Il set di prova sta in `tests/fixtures/symptoms.json`
ed è scritto **prima** dell'implementazione.

---

### Fase 6 — Europe PMC live
*Obiettivo: profondità illimitata senza ingestione illimitata.*

- `retrieval/europepmc.py`, solo open access
- Soglia di confidenza in `fusion.py`, con logging di quando scatta
- Citazioni con DOI e link al full-text

**Accettazione:** una domanda deliberatamente fuori dal corpus locale attiva il
tier 2, e la risposta cita articoli reali e apribili.

---

### Fase 7 — Estensione
*Obiettivo: replicare, non reinventare.*

Torace, poi pelvi, poi arti, poi neuro. Ogni regione è una riesecuzione della
pipeline con un filtro diverso. **Se aggiungere una regione richiede modifiche
all'applicazione, l'architettura è sbagliata e va corretta prima di proseguire.**

---

## 11. Convenzioni di codice

**Python**
- Type hints ovunque, `mypy` in CI
- `pathlib`, mai concatenazione di stringhe per i percorsi
- Gli script della pipeline sono numerati, idempotenti e riprendibili: ognuno
  controlla cosa è già stato fatto e salta
- Tutto l'SQL vive in `api/queries.py` e `pipeline/lib/db.py`. Nessuna query
  inline nelle route
- Nessun ORM

**TypeScript**
- `strict: true`
- I tipi condivisi con il backend si generano dallo schema OpenAPI, non si
  riscrivono a mano
- `FmaId`, `HpoId`, `MondoId` sono branded type, non `string`
- Niente `useEffect` per la logica 3D: si usano gli hook di R3F

**Commit**
- Conventional commits, scope = fase (`feat(fase2): flyTo con easing`)

**Testing**
- La pipeline ha test sui dati, non solo sul codice: conteggi minimi, assenza di
  licenze vuote, integrità referenziale
- `enforce_citations` ha copertura alta: è l'invariante più importante

---

## 12. Glossario

| Sigla | Cos'è | Ruolo qui |
|---|---|---|
| **FMA** | Foundational Model of Anatomy | Chiave primaria delle strutture; già presente nei mesh BodyParts3D |
| **UBERON** | Ontologia anatomica cross-specie | Ponte tra FMA e il mondo clinico |
| **HPO** | Human Phenotype Ontology | Vocabolario dei segni e sintomi; motore della localizzazione |
| **HPOA** | HPO Annotations | Collega malattie e fenotipi, con frequenza |
| **MONDO** | Monarch Merged Disease Ontology | Chiave primaria delle malattie |
| **DO** | Human Disease Ontology | Fornisce gli assiomi malattia → sede |
| **ICD-11** | Classificazione WHO | Codice diagnostico mostrato all'utente |
| **Tier 1/2/3** | Livelli di recupero | Corpus locale / Europe PMC live / sintesi del modello |

---

## 13. Domande aperte

Da risolvere prima delle fasi indicate, non durante.

- **(Fase 1)** Qual è la copertura reale degli xref UBERON→FMA sull'addome? Se
  sotto il 60%, serve un mapping manuale per le strutture principali.
- **(Fase 3)** Quanti documenti StatPearls hanno una licenza che ne consente la
  ridistribuzione, e non solo la lettura? Cambia il modello di distribuzione.
- **(Fase 4)** Validazione clinica: chi controlla che i contenuti siano corretti?
  Serve una persona con formazione medica. Finché non c'è, il codice è pubblico
  come progetto di studio, ma l'applicazione non va offerta come servizio.
- **(Fase 7)** L'istologia (sotto il livello d'organo) richiede asset che
  BodyParts3D non contiene. È un progetto a sé: decidere se affrontarlo o
  fermare la profondità geometrica all'organo, lasciando che i livelli inferiori
  esistano solo nel grafo e nel testo.
