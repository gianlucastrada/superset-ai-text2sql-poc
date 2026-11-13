-- Schema del database "vendite" (dati inventati per la POC).
-- I commenti su tabelle e colonne vengono letti dall'IA per capire i dati:
-- tenerli chiari e aggiornati migliora molto la qualita' del Text-to-SQL.

CREATE TABLE clienti (
    id                  serial PRIMARY KEY,
    nome                text        NOT NULL,
    tipo                text        NOT NULL CHECK (tipo IN ('Privato', 'Azienda')),
    citta               text        NOT NULL,
    regione             text        NOT NULL,
    area                text        NOT NULL CHECK (area IN ('Nord', 'Centro', 'Sud e Isole')),
    data_registrazione  date        NOT NULL
);

CREATE TABLE prodotti (
    id              serial PRIMARY KEY,
    nome            text           NOT NULL,
    categoria       text           NOT NULL,
    prezzo_listino  numeric(10,2)  NOT NULL,
    costo           numeric(10,2)  NOT NULL
);

CREATE TABLE ordini (
    id           serial PRIMARY KEY,
    cliente_id   integer  NOT NULL REFERENCES clienti(id),
    data_ordine  date     NOT NULL,
    canale       text     NOT NULL CHECK (canale IN ('Online', 'Negozio', 'Telefono', 'Agente')),
    stato        text     NOT NULL CHECK (stato IN ('Consegnato', 'Spedito', 'Annullato', 'Reso'))
);

CREATE TABLE righe_ordine (
    id               serial PRIMARY KEY,
    ordine_id        integer        NOT NULL REFERENCES ordini(id),
    prodotto_id      integer        NOT NULL REFERENCES prodotti(id),
    quantita         integer        NOT NULL CHECK (quantita > 0),
    prezzo_unitario  numeric(10,2)  NOT NULL,
    sconto_pct       numeric(5,2)   NOT NULL DEFAULT 0
);

CREATE INDEX ON ordini (data_ordine);
CREATE INDEX ON ordini (cliente_id);
CREATE INDEX ON righe_ordine (ordine_id);
CREATE INDEX ON righe_ordine (prodotto_id);

-- Le viste di analisi (v_vendite, v_vendite_tutte) sono in 05-viste-vendite.sql.

COMMENT ON TABLE clienti      IS 'Anagrafica clienti (privati e aziende) di un negozio di elettronica e articoli per casa/ufficio, con citta, regione e area geografica italiana.';
COMMENT ON TABLE prodotti     IS 'Catalogo prodotti con categoria, prezzo di listino e costo di acquisto.';
COMMENT ON TABLE ordini       IS 'Testata ordini: cliente, data, canale di vendita e stato.';
COMMENT ON TABLE righe_ordine IS 'Righe d''ordine: prodotto, quantita, prezzo unitario applicato e sconto percentuale.';

COMMENT ON COLUMN clienti.tipo                IS 'Privato oppure Azienda';
COMMENT ON COLUMN clienti.area                IS 'Nord, Centro oppure Sud e Isole';
COMMENT ON COLUMN clienti.data_registrazione  IS 'Data in cui il cliente si è registrato';
COMMENT ON COLUMN prodotti.prezzo_listino     IS 'Prezzo di vendita di listino in euro, IVA esclusa';
COMMENT ON COLUMN prodotti.costo              IS 'Costo di acquisto unitario in euro';
COMMENT ON COLUMN ordini.canale               IS 'Canale di vendita: Online, Negozio, Telefono, Agente';
COMMENT ON COLUMN ordini.stato                IS 'Consegnato, Spedito, Annullato (non conta nel fatturato), Reso (merce restituita)';
COMMENT ON COLUMN righe_ordine.prezzo_unitario IS 'Prezzo unitario applicato in euro, prima dello sconto';
COMMENT ON COLUMN righe_ordine.sconto_pct     IS 'Sconto in percentuale (0-100) sul prezzo unitario';
