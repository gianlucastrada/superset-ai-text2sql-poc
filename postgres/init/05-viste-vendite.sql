-- Viste di analisi per l'IA e per Superset.
--
-- v_vendite        = SOLO le vendite valide (ordini annullati gia' esclusi).
--                    Cosi' somme, conteggi e medie sono corretti senza dover ricordare
--                    il filtro sugli annullati (il modello a volte lo dimentica).
-- v_vendite_tutte  = tutte le righe d'ordine, compresi gli annullati: solo per analisi
--                    sugli annullamenti.
--
-- Il file e' idempotente (CREATE OR REPLACE): si usa sia alla prima inizializzazione sia
-- per aggiornare un database gia' esistente (scripts\aggiorna-db.ps1).
-- Solo caratteri ASCII: viene anche inviato a psql da PowerShell.

CREATE OR REPLACE VIEW v_vendite_tutte AS
SELECT
    r.id                                                         AS riga_id,
    o.id                                                         AS ordine_id,
    o.data_ordine,
    date_trunc('month', o.data_ordine)::date                     AS mese,
    o.canale,
    o.stato,
    c.id                                                         AS cliente_id,
    c.nome                                                       AS cliente,
    c.tipo                                                       AS tipo_cliente,
    c.citta,
    c.regione,
    c.area,
    p.id                                                         AS prodotto_id,
    p.nome                                                       AS prodotto,
    p.categoria,
    r.quantita,
    r.prezzo_unitario,
    r.sconto_pct,
    round(r.quantita * r.prezzo_unitario * (1 - r.sconto_pct / 100), 2)              AS importo,
    round(r.quantita * (r.prezzo_unitario * (1 - r.sconto_pct / 100) - p.costo), 2)  AS margine
FROM righe_ordine r
JOIN ordini   o ON o.id = r.ordine_id
JOIN clienti  c ON c.id = o.cliente_id
JOIN prodotti p ON p.id = r.prodotto_id;

-- Stesse colonne, nello stesso ordine, ma senza gli ordini annullati
CREATE OR REPLACE VIEW v_vendite AS
SELECT * FROM v_vendite_tutte WHERE stato <> 'Annullato';

-- v_ordini = UNA riga per ORDINE (tutti gli stati, annullati e resi compresi).
--            Serve per contare gli ordini (annullati, resi, per canale, per mese...):
--            su v_vendite COUNT(*) conta le righe d'ordine, non gli ordini.
CREATE OR REPLACE VIEW v_ordini AS
SELECT
    ordine_id,
    min(data_ordine)           AS data_ordine,
    min(mese)                  AS mese,
    min(canale)                AS canale,
    min(stato)                 AS stato,
    min(cliente_id)            AS cliente_id,
    min(cliente)               AS cliente,
    min(tipo_cliente)          AS tipo_cliente,
    min(regione)               AS regione,
    min(area)                  AS area,
    count(*)                   AS num_righe,
    sum(quantita)              AS num_pezzi,
    sum(importo)               AS importo,
    sum(margine)               AS margine
FROM v_vendite_tutte
GROUP BY ordine_id;

GRANT SELECT ON v_vendite, v_vendite_tutte, v_ordini TO ai_reader;

COMMENT ON VIEW v_vendite IS
  'Vista consigliata per TUTTE le analisi di vendita: fatturato, numero ordini, scontrino medio, margini, clienti, prodotti, canali, aree. Contiene SOLO le vendite valide: gli ordini Annullati sono gia esclusi, quindi NON serve filtrare per stato. Una riga per riga d''ordine: per CONTARE gli ordini usare v_ordini oppure COUNT(DISTINCT ordine_id), mai COUNT(*).';
COMMENT ON VIEW v_vendite_tutte IS
  'Tutte le righe d''ordine COMPRESI gli ordini Annullati. Usare SOLO per analisi sugli annullamenti (es. percentuale di ordini annullati). Per fatturato e vendite usare v_vendite. Una riga per riga d''ordine: per contare gli ordini annullati usare v_ordini.';
COMMENT ON VIEW v_ordini IS
  'Una riga per ORDINE, con TUTTI gli stati (Consegnato, Spedito, Annullato, Reso). Vista da usare per CONTARE ordini: numero di ordini, ordini annullati o resi, percentuale di annullati, ordini per canale o per mese. Per il fatturato usare v_vendite (esclude gli annullati); in questa vista importo e margine includono anche gli annullati.';
COMMENT ON COLUMN v_ordini.stato   IS 'Consegnato, Spedito, Annullato, Reso';
COMMENT ON COLUMN v_ordini.importo IS 'Totale dell''ordine in euro (somma delle righe), anche se annullato';

COMMENT ON COLUMN v_vendite.mese     IS 'Primo giorno del mese dell''ordine, utile per raggruppare per mese';
COMMENT ON COLUMN v_vendite.stato    IS 'Consegnato, Spedito o Reso (gli Annullati non sono presenti in questa vista)';
COMMENT ON COLUMN v_vendite.importo  IS 'Fatturato netto della riga in euro = quantita * prezzo_unitario * (1 - sconto_pct/100). Per il fatturato usare SUM(importo).';
COMMENT ON COLUMN v_vendite.margine  IS 'Margine della riga in euro = importo - quantita * costo';
COMMENT ON COLUMN v_vendite_tutte.stato   IS 'Consegnato, Spedito, Annullato, Reso';
COMMENT ON COLUMN v_vendite_tutte.importo IS 'Importo netto della riga in euro, COMPRESI gli ordini annullati';
