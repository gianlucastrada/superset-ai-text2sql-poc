"""Configurazione di Superset per la POC Text-to-SQL.

Valori sensibili e indirizzi arrivano da variabili d'ambiente (Secret e Deployment in k8s/).
"""

import os

from superset_ai import ai_bp, app_mutator

# Chiave per cifrare sessioni e password delle connessioni: deve restare stabile nel tempo.
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# Metadati di Superset (utenti, dashboard, grafici...) nel database "superset" di Postgres
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_DATABASE_URI"]

# Estensione AI: pagina /ai/, API e pannello per SQL Lab
BLUEPRINTS = [ai_bp]
FLASK_APP_MUTATOR = app_mutator

# SQL Lab sincrono (niente Celery/Redis per la POC)
SQLLAB_TIMEOUT = 60
SUPERSET_WEBSERVER_TIMEOUT = 120

# Il validatore SQL di Postgres richiede il programma 'ecpg', assente nell'immagine:
# senza questa riga SQL Lab segnerebbe un errore (falso) su ogni query.
SQL_VALIDATORS_BY_ENGINE: dict = {}

# Cache in memoria: basta per un singolo pod
CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300}
DATA_CACHE_CONFIG = CACHE_CONFIG

# Accesso solo locale via port-forward (HTTP): cookie non "secure"
SESSION_COOKIE_SECURE = False

FEATURE_FLAGS = {
    "DASHBOARD_RBAC": False,
}
