-- Dati di vendita INVENTATI per la POC: 12 mesi, dal 1 novembre 2025 al 31 ottobre 2026.
-- Generazione deterministica (setseed): ogni installazione produce gli stessi dati.
-- Include stagionalita' (Black Friday, Natale, calo ad agosto), crescita nell'anno
-- e clienti/prodotti piu' attivi di altri, per avere grafici realistici.

SELECT setseed(0.42);

-- ---------------------------------------------------------------- citta
CREATE TEMP TABLE tmp_citta (citta text, regione text, area text, peso int);
INSERT INTO tmp_citta VALUES
  ('Milano','Lombardia','Nord',14), ('Bergamo','Lombardia','Nord',4), ('Brescia','Lombardia','Nord',4),
  ('Torino','Piemonte','Nord',8), ('Genova','Liguria','Nord',4), ('Venezia','Veneto','Nord',4),
  ('Verona','Veneto','Nord',4), ('Padova','Veneto','Nord',4), ('Bologna','Emilia-Romagna','Nord',6),
  ('Modena','Emilia-Romagna','Nord',3), ('Trieste','Friuli-Venezia Giulia','Nord',2), ('Trento','Trentino-Alto Adige','Nord',2),
  ('Firenze','Toscana','Centro',6), ('Pisa','Toscana','Centro',2), ('Roma','Lazio','Centro',13),
  ('Perugia','Umbria','Centro',2), ('Ancona','Marche','Centro',2),
  ('Napoli','Campania','Sud e Isole',8), ('Salerno','Campania','Sud e Isole',2), ('Bari','Puglia','Sud e Isole',5),
  ('Lecce','Puglia','Sud e Isole',2), ('Palermo','Sicilia','Sud e Isole',5), ('Catania','Sicilia','Sud e Isole',4),
  ('Cagliari','Sardegna','Sud e Isole',3), ('Reggio Calabria','Calabria','Sud e Isole',2);

-- Estrazione pesata: ogni citta' ripetuta "peso" volte
CREATE TEMP TABLE tmp_citta_pesate AS
SELECT row_number() OVER () AS n, c.citta, c.regione, c.area
FROM tmp_citta c, generate_series(1, c.peso);

-- ---------------------------------------------------------------- clienti (400)
INSERT INTO clienti (nome, tipo, citta, regione, area, data_registrazione)
SELECT
  CASE WHEN g.privato
       THEN (ARRAY['Marco','Giulia','Luca','Francesca','Alessandro','Sara','Andrea','Chiara','Matteo','Elena',
                   'Lorenzo','Valentina','Davide','Martina','Simone','Federica','Paolo','Laura','Stefano','Anna'])[1 + floor(random()*20)::int]
            || ' ' ||
            (ARRAY['Rossi','Russo','Ferrari','Esposito','Bianchi','Romano','Colombo','Ricci','Marino','Greco',
                   'Bruno','Gallo','Conti','De Luca','Mancini','Costa','Giordano','Rizzo','Lombardi','Moretti'])[1 + floor(random()*20)::int]
       ELSE (ARRAY['Alfa','Beta','Delta','Sigma','Nova','Orion','Vega','Atlas','Zenit','Polaris',
                   'Iride','Aurora','Kappa','Omega','Lyra'])[1 + floor(random()*15)::int]
            || ' ' ||
            (ARRAY['Tech','Servizi','Consulting','Logistica','Studio','Sistemi','Group','Digitale','Impianti','Solutions'])[1 + floor(random()*10)::int]
            || ' ' ||
            (ARRAY['S.r.l.','S.p.A.','S.n.c.','S.r.l.s.'])[1 + floor(random()*4)::int]
  END,
  CASE WHEN g.privato THEN 'Privato' ELSE 'Azienda' END,
  cp.citta, cp.regione, cp.area,
  DATE '2022-01-01' + floor(random() * (DATE '2026-09-30' - DATE '2022-01-01'))::int
FROM (
  SELECT i, random() < 0.72 AS privato,
         1 + floor(random() * (SELECT count(*) FROM tmp_citta_pesate))::int AS n_citta
  FROM generate_series(1, 400) AS i
) g
JOIN tmp_citta_pesate cp ON cp.n = g.n_citta
ORDER BY g.i;

-- ---------------------------------------------------------------- prodotti (60: 6 categorie x 10)
CREATE TEMP TABLE tmp_categorie (categoria text, oggetti text[], prezzo_min numeric, prezzo_max numeric);
INSERT INTO tmp_categorie VALUES
  ('Smartphone',     ARRAY['Smartphone','Telefono','Phone'],               149, 1199),
  ('Informatica',    ARRAY['Notebook','Monitor','Tablet','Desktop'],       129, 1899),
  ('Accessori',      ARRAY['Cuffie','Mouse','Tastiera','Caricatore','Cover','Webcam'], 9, 189),
  ('Elettrodomestici', ARRAY['Aspirapolvere','Friggitrice ad aria','Macchina caffe','Robot da cucina'], 59, 699),
  ('TV e Audio',     ARRAY['Smart TV','Soundbar','Speaker','Proiettore'],  79, 1499),
  ('Ufficio',        ARRAY['Stampante','Sedia ergonomica','Scrivania','Lampada','Router'], 29, 449);

INSERT INTO prodotti (nome, categoria, prezzo_listino, costo)
SELECT
  x.oggetto || ' ' ||
  (ARRAY['Pro','Plus','Lite','Max','Air','One','Neo','Smart','Ultra','Eco'])[1 + floor(random()*10)::int] || ' ' ||
  (100 + floor(random()*900))::int,
  x.categoria,
  x.prezzo,
  round((x.prezzo * (0.55 + random() * 0.20))::numeric, 2)
FROM (
  SELECT c.categoria,
         c.oggetti[1 + floor(random() * array_length(c.oggetti, 1))::int] AS oggetto,
         round((c.prezzo_min + (c.prezzo_max - c.prezzo_min) * power(random(), 1.8))::numeric, 0) - 0.01 AS prezzo
  FROM tmp_categorie c, generate_series(1, 10)
) x
ORDER BY x.categoria;

-- ---------------------------------------------------------------- ordini
-- Ordini al giorno = base * stagionalita' del mese * crescita * giorno della settimana, con rumore.
CREATE TEMP TABLE tmp_giorni AS
SELECT d::date AS giorno,
       greatest(0, round(
         13
         * CASE extract(month FROM d)
             WHEN 11 THEN 1.35 WHEN 12 THEN 1.70 WHEN 1 THEN 0.80 WHEN 2 THEN 0.85
             WHEN 3 THEN 0.95 WHEN 4 THEN 1.00 WHEN 5 THEN 1.00 WHEN 6 THEN 0.95
             WHEN 7 THEN 0.85 WHEN 8 THEN 0.60 WHEN 9 THEN 1.05 WHEN 10 THEN 1.10 END
         * (1 + 0.18 * (d::date - DATE '2025-11-01') / 365.0)
         * CASE WHEN extract(isodow FROM d) IN (6, 7) THEN 0.75 ELSE 1.08 END
         * CASE WHEN d::date BETWEEN DATE '2025-11-24' AND DATE '2025-12-01' THEN 1.6 ELSE 1 END
         * (0.75 + random() * 0.5)
       ))::int AS n_ordini
FROM generate_series(DATE '2025-11-01', DATE '2026-10-31', INTERVAL '1 day') AS d;

INSERT INTO ordini (cliente_id, data_ordine, canale, stato)
SELECT
  1 + floor(400 * power(random(), 1.7))::int,          -- alcuni clienti ordinano molto piu' di altri
  g.giorno,
  CASE WHEN r1 < 0.46 THEN 'Online' WHEN r1 < 0.76 THEN 'Negozio' WHEN r1 < 0.86 THEN 'Telefono' ELSE 'Agente' END,
  CASE WHEN r2 < 0.06 THEN 'Annullato'
       WHEN r2 < 0.10 THEN 'Reso'
       WHEN g.giorno > DATE '2026-10-24' AND r2 < 0.55 THEN 'Spedito'
       ELSE 'Consegnato' END
FROM (
  SELECT t.giorno, random() AS r1, random() AS r2
  FROM tmp_giorni t, generate_series(1, t.n_ordini)
) g
ORDER BY g.giorno;

-- Gli agenti lavorano soprattutto con le aziende: sposto meta' degli ordini "Agente" dei privati sull'Online
UPDATE ordini o SET canale = 'Online'
FROM clienti c
WHERE c.id = o.cliente_id AND c.tipo = 'Privato' AND o.canale = 'Agente' AND random() < 0.5;

-- ---------------------------------------------------------------- righe d'ordine (1-4 per ordine)
INSERT INTO righe_ordine (ordine_id, prodotto_id, quantita, prezzo_unitario, sconto_pct)
SELECT
  x.ordine_id,
  x.prodotto_id,
  CASE WHEN x.tipo = 'Azienda' THEN 1 + floor(power(random(), 2) * 10)::int
       ELSE 1 + floor(power(random(), 3) * 3)::int END,
  p.prezzo_listino,
  CASE WHEN x.r < 0.55 THEN 0 WHEN x.r < 0.75 THEN 5 WHEN x.r < 0.88 THEN 10
       WHEN x.r < 0.96 THEN 15 ELSE 20 END
  + CASE WHEN x.data_ordine BETWEEN DATE '2025-11-24' AND DATE '2025-12-01' THEN 10 ELSE 0 END
FROM (
  SELECT o.id AS ordine_id, o.data_ordine, c.tipo,
         1 + floor(60 * power(random(), 1.4))::int AS prodotto_id,   -- prodotti piu' venduti di altri
         random() AS r
  FROM ordini o
  JOIN clienti c ON c.id = o.cliente_id
  CROSS JOIN LATERAL generate_series(1, 1 + floor(power(random(), 2) * 4)::int + (o.id * 0)) AS n
) x
JOIN prodotti p ON p.id = x.prodotto_id
ORDER BY x.ordine_id;

ANALYZE;
