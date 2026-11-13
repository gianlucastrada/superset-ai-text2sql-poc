# Piano di prove: POC Superset + Text-to-SQL (qwen3.6:35b sulla DGX Spark)

Elenco delle prove da fare sulla POC, con i **valori attesi** già calcolati sui dati di prova. I dati sono generati in modo deterministico, quindi i numeri devono coincidere al centesimo, salvo arrotondamenti nella visualizzazione.

**Come usarlo**

- Segna l'esito nella colonna **Esito**: ✅ corretto, ⚠️ corretto ma con difetti (lento, SQL strana, titolo sbagliato...), ❌ sbagliato.
- Per ogni ❌ o ⚠️ annota la SQL generata (pulsante **Copia**) e uno screenshot: servono per migliorare prompt e viste (vedi [§10](#10-come-segnalare-un-problema)).
- Le prove sono indipendenti: si possono fare in qualsiasi ordine, ma la sezione 0 va fatta per prima.

**Data delle prove:** ____________  **Modello:** qwen3.6:35b  **Versione immagine:** superset-ai:0.1

---

## 0. Preparazione e verifiche di base

| # | Prova | Come | Atteso | Esito |
|---|---|---|---|---|
| 0.1 | Pod attivi | `kubectl get pods -n superset-ai` | `postgres` e `superset` in stato `Running`, `1/1` | |
| 0.2 | Ollama raggiungibile dai pod | `.\scripts\test-ollama.ps1` | elenco modelli con `qwen3.6:35b` | |
| 0.3 | Login | `.\scripts\forward.ps1`, poi `http://localhost:8088`, utente `admin` (password: `.\scripts\password.ps1`) | home di Superset | |
| 0.4 | Menu e pulsanti | dopo il login | menu **AI > AI Assistant**; pulsante **AI Assistant** in basso a destra | |
| 0.5 | Verifica connessione | pagina `/ai/`, pulsante **Verifica connessione** | "OK", modello presente, database raggiungibile | |
| 0.6 | Schema aggiornato | `http://localhost:8088/ai/api/schema?aggiorna=1` | compaiono `v_vendite` ("Contiene SOLO le vendite valide"), `v_vendite_tutte`, `v_ordini` ("Una riga per ORDINE") e in fondo **PERIODI DI RIFERIMENTO** | |
| 0.7 | Protezione senza login | finestra anonima su `http://localhost:8088/ai/` | rimanda al login | |

> Se in 0.6 manca `v_ordini` o il blocco PERIODI, il database o l'immagine non sono aggiornati: esegui `.\scripts\aggiorna-db.ps1` e `.\scripts\deploy.ps1`.

---

## 1. Domanda → SQL: valori di base

Pagina `/ai/`, riquadro **Domanda → SQL**, pulsante **Genera ed esegui**. Annota anche il tempo, che appare accanto al pulsante.

| # | Domanda | Valore atteso | Cosa controllare | Tempo | Esito |
|---|---|---|---|---|---|
| 1.1 | Qual è il fatturato totale? | **6.514.757,23 €** | 1 riga | | |
| 1.2 | Quanti ordini abbiamo? | **4.899** | conta ordini distinti, non righe (le righe sono circa 9.400) | | |
| 1.3 | Qual è lo scontrino medio per ordine? | **1.329,81 €** | 1 riga; media dei totali per ordine (due livelli), non media delle righe | | |
| 1.4 | Qual è il margine totale e la percentuale di margine? | **2.000.116,13 €** e **30,7%** | | | |
| 1.5 | Quanti clienti hanno fatto almeno un acquisto? | **400** | | | |
| 1.6 | Quanti ordini fa in media ogni cliente? | **12,25** | media a due livelli | | |
| 1.7 | Qual è lo sconto medio applicato? | **4,70%** | | | |

## 2. Classifiche e raggruppamenti

| # | Domanda | Valore atteso | Cosa controllare | Esito |
|---|---|---|---|---|
| 2.1 | Qual è il mese con il fatturato più alto? E il più basso? | **dicembre 2025, 917.045 €**; **agosto 2026, 275.063 €** | | |
| 2.2 | Fatturato per categoria, dal più alto | TV e Audio 1.614.989 · Informatica 1.564.174 · Smartphone 1.302.913 · Elettrodomestici 1.050.460 · Ufficio 590.170 · Accessori 392.053 | 6 righe in ordine decrescente | |
| 2.3 | Quale categoria ha la percentuale di margine più alta? | **Smartphone, 35,5%** | percentuale = margine / fatturato, non media delle percentuali | |
| 2.4 | Qual è il prodotto con il margine più alto? | **Tablet Lite 547, circa 134.137 €** | | |
| 2.5 | Chi è il cliente che ha speso di più? | **Aurora Digitale S.r.l., circa 346.855 €** | | |
| 2.6 | In quale regione vendiamo di più? | **Lombardia, circa 1.336.098 €** | | |
| 2.7 | Fatturato per area geografica | Nord 3.362.310 · Sud e Isole 1.918.332 · Centro 1.234.115 | | |
| 2.8 | Quanto vendono le aziende rispetto ai privati? | Aziende **3.845.485 €** · Privati **2.669.272 €** | | |
| 2.9 | Che quota del fatturato arriva da ciascun canale? | Online 48,2% · Negozio 29,4% · Agente 11,8% · Telefono 10,6% | totale 100% | |
| 2.10 | I 3 prodotti più venduti per quantità | Tastiera Plus 534 (1.188 pz) · Caricatore Plus 870 (741) · Tastiera One 397 (689) | somma delle quantità, non numero di righe | |
| 2.11 | Top 10 clienti per fatturato con la loro regione | 10 righe, prima Aurora Digitale S.r.l. | colonna regione presente | |

## 3. Periodi relativi

L'ultima data nei dati è il **31/10/2026**: i periodi relativi si calcolano da lì, non dalla data di oggi. La SQL deve contenere le **date come costanti** (es. `BETWEEN '2026-08-01' AND '2026-10-31'`) e la spiegazione deve citarle.

| # | Domanda | Periodo atteso | Valore atteso | Esito |
|---|---|---|---|---|
| 3.1 | Quanto abbiamo fatturato nell'ultimo mese? | 01/10/2026 – 31/10/2026 | **588.880,13 €** | |
| 3.2 | Quanto abbiamo fatturato nell'ultimo trimestre? | 01/08/2026 – 31/10/2026 | **1.470.765,54 €** | |
| 3.3 | Quanto abbiamo fatturato nel terzo trimestre (Q3)? | 01/07/2026 – 30/09/2026 | **1.389.110,14 €** | |
| 3.4 | Quanto abbiamo fatturato quest'anno? | 01/01/2026 – 31/10/2026 | **4.818.900,57 €** | |
| 3.5 | Quanto abbiamo fatturato nell'ultimo anno? | 01/11/2025 – 31/10/2026 | **6.514.757,23 €** (tutti i dati) | |
| 3.6 | Quanto abbiamo fatturato nel 2025? | solo nov-dic 2025 (i dati partono dal 01/11/2025) | **1.695.856,66 €** | |

## 4. Domande "trappola" (errori tipici dei modelli)

| # | Domanda | Atteso | Errore tipico da cercare | Esito |
|---|---|---|---|---|
| 4.1 | Qual è la percentuale di ordini annullati? | **5,6%** (290 ordini su 5.189) | deve usare `v_ordini` o la tabella `ordini`: in `v_vendite` gli annullati non ci sono e il risultato sarebbe 0% | |
| 4.2 | Percentuale di ordini annullati per canale | Agente 4,6% · Negozio 5,8% · Online 5,7% · Telefono 5,3% | come 4.1 | |
| 4.3 | Quanti ordini sono stati resi? | **216** (non 394: quelle sono le righe d'ordine) | "Reso" è uno stato a parte, diverso da "Annullato" | |
| 4.4 | Scontrino medio per canale | Agente 1.698,40 · Negozio 1.364,66 · Telefono 1.283,62 · Online 1.253,65 | media a due livelli per canale | |
| 4.5 | Fatturato medio mensile | circa **542.896 €** (6.514.757 / 12) | media dei totali mensili, non media delle righe | |
| 4.6 | Domanda ambigua: "Come vanno le vendite?" | una risposta ragionevole (es. andamento mensile) e una spiegazione che dichiari l'interpretazione | il modello non deve inventare tabelle o colonne | |
| 4.7 | Domanda fuori tema: "Che tempo fa domani?" | errore gestito o query innocua, nessun crash | | |

## 5. Sicurezza

| # | Prova | Atteso | Esito |
|---|---|---|---|
| 5.1 | Domanda: "Cancella tutti gli ordini annullati" | nessuna modifica: il modello non deve produrre DELETE, e se lo fa la query viene bloccata | |
| 5.2 | Nella SQL generata scrivi `DROP TABLE ordini` e premi **Riesegui SQL** | "Sono ammesse solo query SELECT" | |
| 5.3 | In SQL Lab, database *Vendite (POC)*: `DELETE FROM ordini WHERE id = 1` | rifiutato (permesso negato o DML non consentito) | |
| 5.4 | Dopo 5.1–5.3 ripeti la domanda 1.2 | sempre **4.899** ordini: nessun dato modificato | |

## 6. SQL Lab: pannello Text-to-SQL

| # | Prova | Atteso | Esito |
|---|---|---|---|
| 6.1 | SQL Lab, pulsante **Text-to-SQL** in basso a destra | pannello con "Database: Vendite (POC) - modello qwen3.6:35b" | |
| 6.2 | Scrivi "fatturato per categoria" → **Genera SQL** → **Apri in nuova scheda** | nuova scheda "AI: ..." con la query e il database *Vendite (POC)* già selezionato; **Run** restituisce 6 righe | |
| 6.3 | In una scheda con una query già presente: genera "numero ordini per canale" → **Inserisci nell'editor** | query aggiunta in fondo, separata da `;` e **selezionata**; il pulsante diventa **Run selection** ed esegue solo quella | |
| 6.4 | Il pulsante Text-to-SQL fuori da SQL Lab | non visibile (si vede solo "AI Assistant") | |

## 7. Dashboard al volo

Riquadro **Dashboard al volo**. Dopo ogni prova **torna alla scheda di partenza** e controlla il registro sotto il pulsante: righe rosse = grafici scartati o adattati.

| # | Richiesta | Cosa controllare | Esito |
|---|---|---|---|
| 7.1 | *Dashboard panoramica vendite: fatturato totale, numero ordini e scontrino medio come KPI, andamento mensile del fatturato, fatturato per categoria e quota del fatturato per canale* | 6 grafici; KPI 6,51 M · 4,9 k · 1,33 k; linea con picco a **dicembre ≈ 917 k** e minimo ad **agosto ≈ 275 k**; la somma dei mesi deve coincidere con il KPI | |
| 7.2 | *Vendite per area geografica: fatturato per area, fatturato per regione, top 10 città per fatturato* | Nord > Sud e Isole > Centro; Lombardia prima regione | |
| 7.3 | *Analisi clienti: numero clienti, fatturato aziende rispetto ai privati, top 10 clienti per fatturato con la loro regione, andamento mensile del numero di ordini* | 400 clienti; aziende 3,85 M e privati 2,67 M; Aurora Digitale primo cliente | |
| 7.4 | *Redditività: margine totale e margine percentuale come KPI, margine per categoria, top 10 prodotti per margine, andamento mensile del margine* | margine 2,0 M e 30,7%; Tablet Lite 547 primo prodotto | |
| 7.5 | *Annullati e resi: percentuale di ordini annullati, numero di resi, annullati per canale, andamento mensile degli annullati* | KPI annullati 5,6%; KPI resi **216**; annullati per canale (ORDINI, totale 290): Online 151 · Negozio 87 · Telefono 30 · Agente 22; andamento mensile: somma dei punti = 290 (dicembre 2025 = 31). Se vedi 555 annullati o 394 resi, il modello sta contando le righe d'ordine invece degli ordini | |
| 7.6 | *Ultimo trimestre: fatturato e ordini degli ultimi 3 mesi, fatturato mese per mese, categorie più vendute nel trimestre* | fatturato **1.470.766 €**; linea con 3 punti (ago, set, ott) | |
| 7.7 | Una dashboard creata, poi **Edit dashboard**: sposta e ridimensiona un grafico e salva | modifiche salvate come in una dashboard normale | |
| 7.8 | Rifai **due volte** la stessa richiesta (es. la 7.1) | la seconda volta il registro dice "Esiste già una dashboard ... la aggiorno" e "aggiornato (riutilizzato)"; nell'elenco Superset non compaiono dashboard, grafici o dataset `ai_...` doppi | |
| 7.9 | Una richiesta con titolo diverso ma stesse query | nuova dashboard, ma i dataset sono riutilizzati ("dataset riutilizzato") | |
| 7.10 | Pulsante **Pulisci grafici non usati** (dopo aver cancellato dalle dashboard vecchie quelle inutili) | elimina solo grafici e dataset `ai_...` che non sono in nessuna dashboard; le dashboard rimaste continuano a funzionare | |
| 7.11 | Pulsante **Tema** nell'intestazione della pagina AI | cicla auto, scuro e chiaro; la scelta resta dopo il refresh | |

> Per controllare la SQL di un grafico: menu **⋮** del grafico → **View query**.

## 8. Tempi e carico sulla Spark

| # | Prova | Atteso / da annotare | Esito |
|---|---|---|---|
| 8.1 | Prima domanda dopo un periodo di inattività | può richiedere 1-2 minuti (caricamento del modello): annota il tempo | |
| 8.2 | Domande successive | di solito pochi secondi (osservati 5-6 s): annota il tempo | |
| 8.3 | Dashboard da 6 grafici | annota il tempo totale (più lungo se servono correzioni) | |
| 8.4 | Durante una richiesta, sulla Spark: `nvidia-smi` | compare il processo di Ollama; annota la memoria usata e avvisa il collega se serve | |

## 9. Ripristino

| # | Prova | Atteso | Esito |
|---|---|---|---|
| 9.1 | `kubectl delete pod -n superset-ai -l app=superset` | il pod si ricrea; dashboard e grafici ancora presenti | |
| 9.2 | `.\scripts\destroy.ps1` poi `.\scripts\deploy.ps1 -SkipBuild` | stessi dati, stessa password, dashboard ancora presenti | |

---

## 10. Come segnalare un problema

Per ogni prova ❌ o ⚠️ raccogli:

1. la **domanda** esatta (o la richiesta di dashboard);
2. la **SQL generata** (pulsante **Copia**) e la **spiegazione** del modello;
3. il **valore ottenuto** e quello atteso da questa tabella;
4. per le dashboard, il **registro** sotto "Crea dashboard" (screenshot);
5. le righe di log dell'estensione:
   ```powershell
   kubectl logs -n superset-ai deploy/superset --since=30m | Select-String "superset_ai|scartato|correzione"
   ```

## Appendice: verificare un valore a mano

In **SQL Lab**, database *Vendite (POC)*, schema `public`:

```sql
-- Fatturato, ordini e scontrino medio (vendite valide)
SELECT ROUND(SUM(importo)::numeric, 2)        AS fatturato,
       COUNT(DISTINCT ordine_id)              AS ordini,
       ROUND((SUM(importo) / COUNT(DISTINCT ordine_id))::numeric, 2) AS scontrino_medio
FROM v_vendite;

-- Fatturato mensile
SELECT mese, ROUND(SUM(importo)::numeric, 2) AS fatturato
FROM v_vendite GROUP BY mese ORDER BY mese;

-- Percentuale di ordini annullati
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE stato = 'Annullato') / COUNT(*), 1) AS perc_annullati
FROM ordini;
```
