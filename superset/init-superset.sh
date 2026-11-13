#!/bin/bash
# Inizializzazione di Superset: eseguita dall'initContainer a ogni avvio del pod.
# Tutti i passi sono idempotenti (si possono ripetere senza danni).
set -euo pipefail

echo "==> Attendo che Postgres sia pronto"
for i in $(seq 1 60); do
  if python -c "import os, sqlalchemy as sa; sa.create_engine(os.environ['SUPERSET_DATABASE_URI']).connect().close()" 2>/dev/null; then
    break
  fi
  if [ "$i" -eq 60 ]; then echo "Postgres non raggiungibile dopo 3 minuti"; exit 1; fi
  sleep 3
done

echo "==> Aggiornamento schema dei metadati"
superset db upgrade

echo "==> Utente amministratore"
superset fab create-admin \
  --username "${ADMIN_USERNAME:-admin}" \
  --firstname Admin --lastname POC \
  --email "${ADMIN_EMAIL:-admin@example.com}" \
  --password "${ADMIN_PASSWORD}" || echo "(utente gia' presente)"

echo "==> Ruoli e permessi"
superset init

echo "==> Connessione al database dei dati: ${AI_DATABASE_NAME}"
superset set-database-uri -d "${AI_DATABASE_NAME}" -u "${AI_DATA_URI}"

echo "==> Inizializzazione completata"
