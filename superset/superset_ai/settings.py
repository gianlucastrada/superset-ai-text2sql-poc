"""Impostazioni lette dalle variabili d'ambiente (vedi k8s/20-superset.yaml)."""

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Ollama sulla DGX Spark (connessione diretta, porta 11434)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://10.100.208.51:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.6:35b")
OLLAMA_TIMEOUT = _int("OLLAMA_TIMEOUT", 240)
# 0 = usa il contesto predefinito del server. Cambiarlo puo' forzare Ollama a ricaricare
# il modello, con impatto sugli altri utenti della Spark: lasciare 0 se non serve.
OLLAMA_NUM_CTX = _int("OLLAMA_NUM_CTX", 0)
# qwen3.6 e' un modello "thinking": il ragionamento esteso rallenta molto le risposte.
OLLAMA_THINK = os.environ.get("OLLAMA_THINK", "false").lower() in ("1", "true", "yes")

# Database dei dati (utente in sola lettura) e nome con cui e' registrato in Superset
AI_DATA_URI = os.environ.get("AI_DATA_URI", "")
AI_DATABASE_NAME = os.environ.get("AI_DATABASE_NAME", "Vendite (POC)")
AI_SCHEMA = os.environ.get("AI_SCHEMA", "public")

# Limiti
MAX_PREVIEW_ROWS = _int("AI_MAX_PREVIEW_ROWS", 200)
MAX_CHARTS = _int("AI_MAX_CHARTS", 6)
SCHEMA_CACHE_SECONDS = _int("AI_SCHEMA_CACHE_SECONDS", 600)
