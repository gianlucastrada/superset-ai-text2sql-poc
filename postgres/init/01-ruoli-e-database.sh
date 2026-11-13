#!/bin/sh
# Eseguito UNA volta, al primo avvio di Postgres (volume vuoto).
# Crea:
#   - il database "superset" (metadati di Superset) con il suo utente
#   - l'utente "ai_reader", che verra' usato in sola lettura per i dati di vendita
# Il database "vendite" viene creato dall'immagine postgres tramite POSTGRES_DB.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v superset_pw="$SUPERSET_DB_PASSWORD" \
     -v reader_pw="$AI_READER_PASSWORD" <<'EOSQL'
CREATE ROLE superset LOGIN PASSWORD :'superset_pw';
CREATE DATABASE superset OWNER superset;
CREATE ROLE ai_reader LOGIN PASSWORD :'reader_pw';
EOSQL
