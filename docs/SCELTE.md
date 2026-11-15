# Scelte tecniche e misure

Le decisioni di progetto che non stanno nel [README](../README.md), con il loro perché
e i numeri misurati. Il brief completo, con invarianti e roadmap, è in
[SPEC.md](../SPEC.md).

## Pipeline

Ogni script è idempotente e salta ciò che ha già fatto. Nessun ID viene costruito: ciò
che non si trova nei file scaricati finisce nella tabella `unmapped` (invariante I5).
Dopo ogni esecuzione vanno letti i report in `data/reports/`: `coverage.md`,
`unmapped_<regione>.md`, `is_a_links.md`, `documents.md`.

## Anatomia e ontologie (Fasi 1, 2, 7)

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
- **Ereditarietà dalla classe più generale.** Se, anche con il lato, una struttura
  non raggiunge patologie o segni, eredita quelli dell'antenato FMA più vicino
  (catena di `subClassOf` dichiarati) il cui termine UBERON ne porta: *Right fourth
  rib* ⊑ *Fourth rib* ⊑ *Rib* (`pipeline/lib/taxonomy.py`, basis `fma_is_a`). Al più
  `ISA_MAX_HOPS` passi e antenati con al più `ISA_MAX_DESCENDANTS` sottoclassi, per non
  arrivare a "Organ". La scheda dice che le voci valgono per la classe generale e cita
  FMA. Limiti da tarare leggendo `data/reports/is_a_links.md`.
- **Fenotipi bilaterali.** Un fenotipo che HPO dichiara bilaterale (nome con la parola
  "bilateral", o modificatore "Bilateral" nella definizione logica) non compare sulle
  strutture con un solo lato: "Right kidney" eredita da "kidney", ma non la "Bilateral
  renal agenesis". `phenotype.bilateral` e `structure.sided` li marca 03; il filtro è in
  `api/queries.py`.
- **Nomi italiani.** Da FMA quando li ha; altrimenti dall'etichetta italiana della voce
  Wikidata con lo stesso FMA ID (P1402, dati CC0), solo se il legame è uno a uno
  (`pipeline/lib/wikidata.py`). `structure.label_it_source` dice da dove viene; la
  scheda cita la voce Wikidata.
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

## Corpus testuale e ricerca (Fase 3)

- **Licenze, documento per documento (I3).** MedlinePlus: i riassunti dei temi sono
  pubblico dominio (https://medlineplus.gov/about/using/usingcontent/). Orphanet: la
  CC BY 4.0 è dichiarata nel file Orphadata. StatPearls: ogni capitolo dichiara la sua
  licenza nel file; al 13/11/2026 8.660 capitoli su 8.661 sono CC BY-NC-ND 4.0 (uno CC
  BY 4.0). È la risposta alla domanda aperta della SPEC §13: si possono ridistribuire,
  **senza modifiche e non a fini commerciali**. I chunk sono estratti testuali non
  modificati; la scheda rimanda sempre al capitolo originale.
- **StatPearls solo dall'FTP ufficiale NCBI** (SPEC §3): un unico archivio da ~2 GB,
  letto in streaming senza estrarlo. I capitoli "(Archived)" e le versioni
  "nurse-article" si saltano; i rimandi bibliografici `[1]` si tolgono dal testo (nella
  Fase 4 i marcatori `[n]` sono quelli delle citazioni dell'assistente).
- **Legami solo da riferimenti dichiarati (I5)** (`pipeline/lib/doclinks.py`): codici
  MeSH e ORPHAcode tramite le equivalenze esatte di MONDO, MONDO citato da Orphanet,
  MeSH anatomici tramite UBERON, titolo dei capitoli di anatomia ("Anatomy, Abdomen and
  Pelvis, Liver") per nome esatto, titolo dei capitoli su una malattia per nome o
  sinonimo EXACT di MONDO. Dalla malattia si arriva alla sua sede, anche risalendo
  `part_of` di UBERON di al più due passi ma mai fino a un apparato intero. Ogni legame
  registra `basis` e `via`; la scheda li mostra.
- **Embedding.** `intfloat/multilingual-e5-base` (MIT) in locale, con i prefissi
  `query:`/`passage:` di E5; `sqlite-vec` con distanza coseno. Senza GPU l'indice
  completo (~140.000 chunk) richiede ore: `--first-chunks 1` fa una prova rapida
  sull'apertura di ogni documento. L'API codifica la domanda con lo stesso modello
  registrato in `embedding_meta`.

## Dal sintomo al corpo e letteratura (Fasi 5, 6)

- **Dal sintomo al corpo** (`POST /locate`). La sede di un fenotipo è quella della sua
  definizione logica HPO o, se manca, quella dell'antenato is_a più vicino che la
  dichiara (semantica della sottoclasse: "Back pain" è un'"Abnormality of the
  vertebral column"). Una sede non in scena sale al "tutto" più vicino (part_of), mai a
  una struttura larga. Ogni fenotipo cita HPO, e l'antenato quando la sede è
  ereditata. Il testo scritto non viene salvato. Un vettore per nome e sinonimo di
  fenotipo, con un modello proprio (`LOCATE_MODEL`, e5-large): 19/20 sulle frasi di
  prova contro 15/20 di e5-base.
- **Letteratura** (`GET /structure/{id}/literature`): Europe PMC in tempo reale, solo
  open access, ricerca per nome della struttura (senza lato) in titoli e abstract.
  Mai ingerita né salvata; ogni articolo porta la licenza che Europe PMC dichiara.
- **L'assistente con citazioni (Fase 4) non è stato realizzato.**

## Interfaccia

Il linguaggio visivo è quello della tavola anatomica: scena sul verde dei teli
chirurgici, scheda chiara, un solo accento (iodio), linea di richiamo dall'organo
al suo nome. I token sono in `web/src/index.css`; le tinte dei tessuti e le modalità
di gruppo (pieno, velato, nascosto) in `web/src/scene/tissues.ts`. I caratteri
(Brygada 1918, Hanken Grotesk, entrambi SIL OFL) sono serviti in locale: nessuna
richiesta a terzi.

- **Strati.** Il comando "Strato: Pelle → Muscoli → Ossa → Organi" toglie ciò che sta
  sopra il livello scelto e vela ciò che sta sotto. Il tessuto di ogni struttura
  (`structure.tissue`) lo scrive 04 risalendo la tassonomia FMA fino a classi cercate
  per nome ("Muscle organ", "Bone organ", "Skin"…, `TISSUE_CLASSES` in
  `pipeline/lib/config.py`); le voci della legenda restano regolabili una per una.
- **Contorno.** La struttura selezionata ha un contorno color iodio (drei `Outlines`).
- **Misure di Fase 2.** Con `?perf` nell'indirizzo (es. `http://localhost:5173/?perf`)
  compare un riquadro con il tempo di caricamento, gli fps e il 95° percentile della
  durata dei frame, confrontati con gli obiettivi della SPEC (< 3 s, 60 fps). Va letto
  su uno schermo reale ruotando la scena: in un browser senza GPU gli fps non contano.

## Misure sui dati reali

Pipeline completa su un portatile con NVIDIA RTX 5060 (novembre 2026):

- **Corpus:** 16.573 documenti, tutti con licenza accertata: MedlinePlus 1.014
  (pubblico dominio), Orphanet 6.898 (CC BY 4.0), StatPearls 8.661 (8.660 CC BY-NC-ND
  4.0, 1 CC BY 4.0). 140.452 chunk indicizzati; 16.573 titoli; 17.258 nomi di fenotipo.
- **Test:** 135 passati, inclusi i criteri di accettazione sui dati reali.
- **Ricerca nei testi** (`tests/fixtures/search_queries.json`, 20 domande in italiano,
  soglia 18 nei primi 5): 16/20 con i soli paragrafi; 17/20 unendo titoli e paragrafi
  per distanza (i titoli dominavano); sopra soglia con la fusione per posizione
  (Reciprocal Rank Fusion). "Ittero nel neonato" resta sbagliata.
- **Dal sintomo al corpo** (`tests/fixtures/symptoms.json`, 20 sintomi in italiano
  colloquiale, scritti prima del codice, soglia 16): e5-base con un vettore per
  fenotipo 12/20; un vettore per nome e sinonimo 15/20; e5-large 19/20. I nomi italiani
  del progetto di traduzione di HPO, quasi tutti automatici, peggiorano (13/20): non
  usati.
- **Strutture addominali con `uberon_id` senza documenti:** 78 → 25 con l'ereditarietà
  dal contenitore → 19 con le varianti di nome. Le 19 rimaste sono strutture di cui
  nessuna fonte parla (arteria gastroduodenale, vene frenica e testicolare, perineo…):
  accettate come lacune; la voce "Letteratura" le copre con Europe PMC.
- **Ricerca su sqlite-vec:** una ricerca KNN dentro un JOIN veniva ripetuta per ogni
  riga dell'altra tabella (150 s per domanda su 140.000 chunk); da sola, 20 ricerche in
  0,4 s. Un test impedisce i JOIN nelle query con `MATCH`.

## Limiti noti

- **BodyParts3D 4.0** (insieme part-of) non ha la superficie dei polmoni (solo vie
  bronchiali e vasi), né milza e tiroide; ha pochi muscoli scheletrici.
- **FMA** si scarica solo in HTTP dal server dell'Università di Washington: in un
  ambiente che lascia passare solo HTTPS la pipeline completa non gira (01 prova una
  copia d'archivio dichiarata in `pipeline/lib/config.py`).
- **Copertura clinica disomogenea** tra regioni: vedi `data/reports/coverage.md`.
- **Nessuna validazione clinica:** i contenuti non sono stati controllati da una persona
  con formazione medica (SPEC §13).

## Note per chi sviluppa su Windows

- Eseguire Python con `PYTHONUTF8=1` (nel Prompt dei comandi: `set PYTHONUTF8=1`).
- L'API parte senza riavvio automatico: il reloader di uvicorn manda un Ctrl+C a tutta
  la console. Chi modifica `api/` può usare `npm run dev:api:reload` in un terminale a
  parte.
- PyTorch da PyPI su Windows è solo per CPU: per la GPU installare prima la versione
  CUDA (`https://pytorch.org/get-started/locally/`); le schede della serie RTX 50
  richiedono CUDA 12.8 o successiva.
- Un vecchio accesso a Hugging Face scaduto blocca il download dei modelli, che sono
  pubblici: `.venv\Scripts\hf auth logout`.
