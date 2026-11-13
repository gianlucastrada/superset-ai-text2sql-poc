"""
superset_ai - estensione Text-to-SQL per Apache Superset (POC).

- Pagina "AI Assistant" (/ai/): domanda in italiano -> SQL -> risultati, e dashboard create al volo.
- Pannello "Text-to-SQL" dentro SQL Lab: genera la query e la inserisce nell'editor.
- Modello: Ollama (default qwen3.6:35b sulla DGX Spark).

Si aggancia a Superset tramite superset_config.py:
    BLUEPRINTS = [ai_bp]
    FLASK_APP_MUTATOR = app_mutator
"""

from .views import ai_bp, app_mutator

__all__ = ["ai_bp", "app_mutator"]
