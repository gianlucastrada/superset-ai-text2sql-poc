> Italian documentation (original). The main README is [README.md](README.md) (English).

# POC: Superset con Text-to-SQL e dashboard al volo (Ollama sulla DGX Spark)

Superset 6.1.0 su Kubernetes (Docker Desktop) con un'estensione che usa il modello **qwen3.6:35b** di Ollama sulla DGX Spark per:

- **AI Assistant** (menu **AI > AI Assistant**, oppure pulsante in basso a destra): domanda in italiano, poi query SQL, risultati e **dashboard creata al volo** (KPI, andamento, barre, torta, tabella).
- **Text-to-SQL dentro SQL Lab**: pulsante **Text-to-SQL** in basso a destra. Genera la query e la apre in una nuova scheda di SQL Lab, oppure la inserisce (selezionata) nell'editor corrente.

I dati sono **inventati**: un negozio di elettronica con 400 clienti, 60 prodotti e circa 5.300 ordini (10.000 righe) da novembre 2025 a ottobre 2026.

```
 Browser ──port-forward 8088──► Superset (pod)  ── SQL, utente in sola lettura ──► Postgres (pod)
   │                              │  estensione superset_ai                          ├─ db "vendite"  (dati)
   │                              │                                                  └─ db "superset" (metadati)
   │                              └── HTTP 11434 ──► Ollama sulla DGX Spark (10.100.208.51), qwen3.6:35b
   └─ REST API di Superset (crea dataset, grafici, dashboard con i permessi dell'utente collegato)
```

---

## Prerequisiti

1. Docker Desktop con **Kubernetes attivo** (contesto `docker-desktop`), con almeno 4 GB di RAM e 2 CPU assegnati.
2. PC in ufficio o in VPN: la Spark (`10.100.208.51`) deve essere raggiungibile.
3. **Avvisa il collega della Spark**: `qwen3.6:35b` occupa circa 22 GB di memoria quando viene caricato su una macchina condivisa.

## Avvio (PowerShell, dalla cartella del progetto)

```powershell
cd C:\Users\G.Strada\Documents\02_PROGETTI\AI\Accesso_spark\superset-ai-poc

# Se PowerShell blocca gli script:
Set-ExecutionPolicy -Scope Process Bypass

# 1. Verifica che i pod raggiungano Ollama sulla Spark
.\scripts\test-ollama.ps1

# 2. Build dell'immagine e deploy di Postgres + Superset (stampa la password di admin)
.\scripts\deploy.ps1

# 3. Port-forward, poi apri http://localhost:8088  (utente admin)
.\scripts\forward.ps1
```

Al primo avvio:

- `docker build` scarica `apache/superset:6.1.0` (circa 1-2 GB);
- Postgres crea i database e genera i dati (pochi secondi);
- Superset esegue le migrazioni e crea l'utente admin e la connessione **Vendite (POC)** (1-2 minuti).

Altri script:

| Script | Cosa fa |
|---|---|
| `.\scripts\password.ps1` | mostra la password di admin |
| `.\scripts\deploy.ps1 -SkipBuild` | riapplica la configurazione senza ricostruire l'immagine |
| `.\scripts\deploy.ps1 -Model qwen3-coder:30b -SkipBuild` | cambia modello |
| `.\scripts\deploy.ps1 -OllamaUrl http://host.docker.internal:11435 -SkipBuild` | cambia l'indirizzo di Ollama (vedi sotto) |
| `.\scripts\aggiorna-db.ps1` | riapplica le viste di analisi (`05-viste-vendite.sql`) al database esistente e riavvia Superset |
| `.\scripts\destroy.ps1` | ferma i pod (dati e password restano) |
| `.\scripts\destroy.ps1 -Purge` | cancella tutto, dati compresi |

---

Per verificare la POC con domande e valori attesi: **[PROVE.md](PROVE.md)**.

## Come si usa

### AI Assistant (`http://localhost:8088/ai/`)

- **Domanda → SQL**: scrivi per esempio *"Top 10 prodotti per margine"* e premi **Genera ed esegui** (o Ctrl+Invio). Vedi la spiegazione, la SQL (modificabile, con **Riesegui SQL**) e i risultati. **Apri in SQL Lab** porta la query in una nuova scheda.
- **Dashboard al volo**: descrivi la dashboard, per esempio *"Panoramica vendite: KPI, andamento mensile, categorie e canali"*. Il modello progetta da 3 a 6 grafici. L'estensione esegue ogni query, corregge colonne e tipo di grafico in base ai dati reali, e chiede una correzione al modello se una query fallisce. Poi crea dataset, grafici e dashboard e la apre in una nuova scheda. I grafici con query ancora non valide vengono scartati e indicati nel registro.
- **Verifica connessione** (in alto) controlla Ollama, la presenza del modello e il database.

### SQL Lab

Pulsante **Text-to-SQL** in basso a destra (visibile solo in SQL Lab):

- **Apri in nuova scheda**: crea una scheda "AI: ..." con la query e il database *Vendite (POC)* già selezionato.
- **Inserisci nell'editor**: accoda la query a quella della scheda corrente separandola con `;` e la seleziona, così **Run** esegue solo quella. Se non c'è nessuna scheda aperta, ne apre una nuova.

Le query vengono sempre generate per il database *Vendite (POC)*.

---

## Sicurezza della POC

- Tutte le query sui dati usano l'utente Postgres **`ai_reader`**, che ha **solo permessi SELECT**, transazioni in sola lettura e un timeout di 30 secondi. È la protezione principale: anche una query di modifica verrebbe rifiutata dal database (verificato).
- In più l'estensione accetta solo **una singola SELECT** (controllo con sqlglot) prima di eseguirla.
- Anche SQL Lab usa `ai_reader`, quindi nella POC non si possono modificare i dati da Superset.
- Pagina e API richiedono il login di Superset. La protezione CSRF e la Content Security Policy di Superset restano attive: gli script dell'estensione usano il nonce.
- **Cosa esce dal PC**: schema del database (tabelle, colonne, commenti, valori tipici delle colonne a bassa cardinalità) e le tue domande vanno alla Spark. I risultati delle query no. Per dati aziendali reali chiedi prima l'autorizzazione.
- Le password sono generate casualmente da `deploy.ps1` e stanno nel Secret `superset-ai-secrets`.

---

## Se i pod non raggiungono la Spark

`test-ollama.ps1` prova la connessione prima dal PC, poi da un pod temporaneo.

- **Fallisce anche dal PC**: non sei in VPN/ufficio, oppure un firewall blocca la porta 11434.
- **Funziona dal PC ma non dal pod**: un caso possibile è che `10.100.208.51` cada nell'intervallo di indirizzi interni dei Service di Kubernetes di Docker Desktop (di solito `10.96.0.0/12`, cioè da 10.96.0.0 a 10.111.255.255) e che il cluster lo intercetti. In quel caso fai passare il traffico dal tuo PC.

  **Soluzione A, tunnel SSH** (una finestra PowerShell da tenere aperta):
  ```powershell
  ssh -N -L 0.0.0.0:11435:localhost:11434 dgx@10.100.208.51
  .\scripts\deploy.ps1 -OllamaUrl http://host.docker.internal:11435 -SkipBuild
  ```

  **Soluzione B, inoltro di Windows** (PowerShell come amministratore, resta attivo anche dopo il riavvio):
  ```powershell
  netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=11435 connectaddress=10.100.208.51 connectport=11434
  .\scripts\deploy.ps1 -OllamaUrl http://host.docker.internal:11435 -SkipBuild
  # per toglierlo: netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=11435
  ```

  Poi verifica con `.\scripts\test-ollama.ps1 -OllamaUrl http://host.docker.internal:11435`.

---

## Risoluzione problemi

```powershell
kubectl get pods -n superset-ai
kubectl logs -n superset-ai deploy/superset -c init     # inizializzazione di Superset
kubectl logs -n superset-ai deploy/superset             # server Superset (errori dell'estensione inclusi)
kubectl logs -n superset-ai deploy/postgres
kubectl describe pod -n superset-ai -l app=superset
```

- **Risposte lente o timeout**: la prima richiesta carica `qwen3.6:35b` sulla Spark e può richiedere 1-2 minuti. Il limite è di 240 secondi (variabile `OLLAMA_TIMEOUT`). Il ragionamento esteso ("thinking") del modello è disattivato per velocità (`OLLAMA_THINK=false`).
- **"Il modello non ha restituito un JSON valido"**: riprova. Se succede spesso, prova `qwen3-coder:30b`.
- **Query sbagliate**: la qualità dipende molto dai **commenti** su tabelle e colonne in `postgres/init/02-schema-vendite.sql` e `05-viste-vendite.sql`. Sono il modo più efficace per spiegare i dati al modello. Lo schema letto dall'IA è visibile su `http://localhost:8088/ai/api/schema?aggiorna=1`.
- **Regole di business nei dati, non nel prompt**: il modello a volte dimentica i filtri, per esempio l'esclusione degli ordini annullati. Per questo `v_vendite` contiene già solo le vendite valide, mentre gli annullati sono in `v_vendite_tutte`. Per contare gli ordini c'è `v_ordini` (una riga per ordine): su `v_vendite` `COUNT(*)` conterebbe le righe d'ordine, e un controllo automatico lo segnala al modello. Conviene fare lo stesso con altre regole: viste che restituiscono già i dati "giusti".
- **Pod `superset` in `ErrImageNeverPull`/`ImagePullBackOff`**: l'immagine locale non è visibile al cluster. Controlla che il contesto sia `docker-desktop` e rilancia `deploy.ps1`.
- **Ho cancellato il Secret ma non i dati**: Postgres ha ancora le vecchie password. Usa `destroy.ps1 -Purge` e rifai il deploy.
- **Non vedo la voce di menu AI**: c'è comunque il pulsante **AI Assistant** in basso a destra in ogni pagina, oppure vai su `/ai/`.

---

## Struttura

```
superset-ai-poc\
  README.md
  PROVE.md                           piano di prove con i valori attesi
  postgres\init\                     eseguiti al primo avvio di Postgres (ConfigMap postgres-init)
    01-ruoli-e-database.sh           db "superset", utenti superset e ai_reader
    02-schema-vendite.sql            tabelle, vista v_vendite, commenti per l'IA
    03-dati-vendite.sql              dati inventati (deterministici)
    04-permessi.sql                  ai_reader in sola lettura
    05-viste-vendite.sql             v_vendite (solo vendite valide), v_vendite_tutte, v_ordini (una riga per ordine)
  superset\
    Dockerfile                       apache/superset:6.1.0 + psycopg2 + estensione
    superset_config.py               configurazione (BLUEPRINTS, FLASK_APP_MUTATOR, ...)
    init-superset.sh                 migrazioni, admin, permessi, connessione dati (initContainer)
    superset_ai\                     estensione
      views.py                       pagina /ai/, API, hook su Superset (menu + template)
      llm.py                         client Ollama e prompt (Text-to-SQL, progettazione dashboard)
      dati.py                        esecuzione query in sola lettura e descrizione dello schema
      sqlguard.py                    validazione SQL (una sola SELECT)
      settings.py                    variabili d'ambiente
      templates\superset_ai\assistant.html
      templates\override\tail_js_custom_extra.html   carica il pannello in ogni pagina
      static\assistant.js            pagina AI Assistant + creazione dashboard via REST API
      static\sqllab.js               pulsanti flottanti e pannello di SQL Lab
  k8s\
    00-namespace.yaml                namespace superset-ai
    10-postgres.yaml                 PVC, Deployment, Service
    20-superset.yaml                 Deployment (con initContainer), Service
  scripts\
    deploy.ps1  forward.ps1  password.ps1  test-ollama.ps1  destroy.ps1
```

## Variabili utili (Deployment `superset`)

| Variabile | Default | Note |
|---|---|---|
| `OLLAMA_URL` | `http://10.100.208.51:11434` | via ConfigMap `superset-ai-config` (`deploy.ps1 -OllamaUrl`) |
| `OLLAMA_MODEL` | `qwen3.6:35b` | via ConfigMap (`deploy.ps1 -Model`) |
| `OLLAMA_TIMEOUT` | `240` | secondi |
| `OLLAMA_THINK` | `false` | `true` attiva il ragionamento esteso (molto più lento) |
| `OLLAMA_NUM_CTX` | `0` | `0` = contesto predefinito del server. Cambiarlo può far ricaricare il modello sulla Spark |
| `AI_MAX_CHARTS` | `6` | grafici massimi per dashboard |

## Cosa è stato verificato prima della consegna

Su **Superset 6.1.0 reale** e **Postgres 16 reale**, con un Ollama simulato (la Spark non era raggiungibile dall'ambiente di sviluppo):

- **Database**: gli script di inizializzazione funzionano; dati e stagionalità sono realistici; `ai_reader` non può scrivere né creare tabelle, nemmeno disattivando la sola lettura della sessione.
- **Inizializzazione di Superset**: `init-superset.sh` (migrazioni, admin, permessi, connessione) funziona ed è ripetibile.
- **Accesso**: senza login la pagina reindirizza al login e le API rispondono 401.
- **Browser** (Chromium), con la Content Security Policy attiva e senza violazioni:
  - login e voce di menu "AI";
  - domanda → SQL → risultati;
  - correzione automatica di una query sbagliata;
  - blocco di `DROP`/`DELETE`;
  - creazione di una dashboard con 6 grafici (KPI, linea, barre, torta, tabella) disegnati correttamente, con scarto del grafico con SQL non valida;
  - SQL Lab: apertura in nuova scheda con database preselezionato, esecuzione (12 righe), inserimento e selezione nell'editor esistente.

**Non verificato**: la build dell'immagine e il deploy sul tuo Docker Desktop, gli script PowerShell (non eseguibili nell'ambiente di sviluppo), e **la qualità delle risposte del vero `qwen3.6:35b`**. Il modello reale può sbagliare più spesso del simulato: la correzione automatica e la verifica delle query servono proprio a questo.

## Limiti della POC

- Un solo database (*Vendite (POC)*) per l'IA; nessun filtro nativo nelle dashboard create.
- SQL Lab sincrono e cache in memoria (niente Celery/Redis): va bene per un utente.
- Il pannello di SQL Lab è aggiunto con JavaScript sopra l'interfaccia di Superset. Un aggiornamento importante di Superset potrebbe richiedere di adattarlo (le dashboard usano invece le REST API ufficiali).
