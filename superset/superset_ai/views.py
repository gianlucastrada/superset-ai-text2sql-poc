"""Blueprint Flask dell'estensione e hook di avvio per Superset."""

from __future__ import annotations

import logging
import os
import re
from functools import wraps
from typing import Any, Callable

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from jinja2 import ChoiceLoader, FileSystemLoader

from . import dati, llm, settings
from .sqlguard import SqlNonValida, controlla_logica, valida

logger = logging.getLogger(__name__)

_QUI = os.path.dirname(os.path.abspath(__file__))

ai_bp = Blueprint(
    "superset_ai",
    __name__,
    url_prefix="/ai",
    template_folder=os.path.join(_QUI, "templates"),
    static_folder=os.path.join(_QUI, "static"),
    static_url_path="/static",
)


# --------------------------------------------------------------------------- utilita'

def _errore(messaggio: str, codice: int = 400):
    return jsonify({"errore": messaggio}), codice


def _richiede_login_api(f: Callable) -> Callable:
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any):
        if not current_user or not current_user.is_authenticated:
            return _errore("Accesso richiesto: effettua il login in Superset.", 401)
        return f(*args, **kwargs)

    return wrapper


_RE_COLONNA = re.compile(r'column "(?:[^".]+\.)?([^".]+)" does not exist')


def _errore_db(ex: Exception) -> str:
    """Messaggio d'errore utile al modello: testo di Postgres (con HINT) + dove si trova
    davvero la colonna mancante, se esiste in un'altra tabella/vista."""
    righe = [
        r.strip()
        for r in str(ex).strip().splitlines()
        if r.strip() and not r.strip().startswith("LINE ") and set(r.strip()) != {"^"}
    ]
    testo = " ".join(righe[:3]) or type(ex).__name__
    if m := _RE_COLONNA.search(testo):
        colonna = m.group(1)
        try:
            dove = dati.dove_si_trova(colonna)
        except Exception:  # noqa: BLE001
            dove = []
        if dove:
            testo += (
                f" | Suggerimento: la colonna {colonna} esiste solo in: {', '.join(dove)}. "
                "Usa quella tabella o vista (oppure la JOIN corretta)."
            )
        else:
            testo += f" | La colonna {colonna} non esiste in nessuna tabella: usa solo le colonne dello schema."
    return testo


def _id_database() -> int | None:
    """Id del database dei dati registrato in Superset (serve per SQL Lab e per i dataset)."""
    from superset.extensions import db
    from superset.models.core import Database

    rec = (
        db.session.query(Database)
        .filter_by(database_name=settings.AI_DATABASE_NAME)
        .one_or_none()
    )
    return rec.id if rec else None


def _genera_ed_esegui(domanda: str, esegui: bool, tentativi: int = 2) -> dict[str, Any]:
    """Domanda -> SQL validata (-> risultati). Se il database da errore, chiede una correzione."""
    schema = dati.descrivi_schema()
    risposta = llm.genera_sql(domanda, schema)
    ultimo_errore = ""
    for tentativo in range(tentativi):
        ultimo = tentativo + 1 == tentativi
        try:
            sql = valida(risposta["sql"])
        except SqlNonValida as ex:
            ultimo_errore = str(ex)
        else:
            # Errori logici tipici (es. GROUP BY su colonna non restituita): si chiede una correzione;
            # all'ultimo tentativo la query viene eseguita comunque, con un avviso.
            avviso = controlla_logica(sql)
            if avviso and not ultimo:
                ultimo_errore = avviso
            else:
                try:
                    # Senza esecuzione (SQL Lab) verifica comunque che la query giri, con 1 riga
                    risultato = dati.esegui_query(sql, limite=None if esegui else 1)
                    uscita = {**risposta, "sql": sql, "tentativi": tentativo + 1}
                    if esegui:
                        uscita["risultato"] = risultato
                    if avviso:
                        uscita["avviso"] = avviso
                    return uscita
                except Exception as ex:  # noqa: BLE001
                    ultimo_errore = _errore_db(ex)
        if not ultimo:
            logger.info("Text-to-SQL: correzione richiesta al modello (%s)", ultimo_errore)
            risposta = llm.correggi_sql(domanda, risposta["sql"], ultimo_errore, schema)
    return {**risposta, "errore_sql": ultimo_errore}


def _primo(colonne: list[str], tipi: list[str], voluto: str, ammessi: set[str]) -> str:
    if voluto in colonne and tipi[colonne.index(voluto)] in ammessi:
        return voluto
    for c, t in zip(colonne, tipi):
        if t in ammessi:
            return c
    return ""


# Forma dei dati che ogni tipo di grafico richiede (usata nelle richieste di correzione)
_FORMA = {
    "big_number": "1 sola riga con 1 colonna numerica (il valore del KPI).",
    "bar": "2 colonne: x = categoria (testo) e y = valore numerico; una riga per categoria "
           "(almeno 2, al massimo 15), ordinate per y decrescente.",
    "pie": "2 colonne: x = categoria (testo) e y = valore numerico; da 2 a 8 righe.",
    "line": "2 colonne: x = data di tipo date (es. date_trunc('month', data_ordine)::date AS mese) "
            "e y = valore numerico; UNA RIGA PER PERIODO (es. una per mese, almeno 2), ordinata per x. "
            "Serve GROUP BY sul periodo.",
    "table": "piu' colonne di dettaglio, al massimo 50 righe.",
}


def _problema_forma(tipo: str, colonne: list[str], tipi: list[str], n: int) -> str | None:
    """Controlla che i dati abbiano la forma adatta al tipo di grafico."""
    numerici = [c for c, t in zip(colonne, tipi) if t == "numerico"]
    date = [c for c, t in zip(colonne, tipi) if t == "data"]
    testi = [c for c, t in zip(colonne, tipi) if t == "testo"]
    if n == 0:
        return "La query non restituisce righe."
    if tipo == "big_number" and (n != 1 or not numerici):
        return f"Per un KPI serve 1 riga con un valore numerico, ma la query restituisce {n} righe."
    if tipo == "line" and (not date or n < 2 or not numerici):
        motivo = f"la query restituisce {n} righe" + ("" if date else " e nessuna colonna di tipo data")
        return f"Per un grafico a linee servono una colonna data e una riga per periodo: {motivo}."
    if tipo in ("bar", "pie") and (n < 2 or not (testi or date) or not numerici):
        return (f"Per un grafico a {'barre' if tipo == 'bar' else 'torta'} servono una colonna di "
                f"categorie e piu' righe, ma la query restituisce {n} righe.")
    return None


def _verifica_grafico(g: dict[str, Any], richiesta: str, schema: str) -> dict[str, Any]:
    """Valida ed esegue la SQL di un grafico. Se la query fallisce o i dati non hanno la forma
    adatta al tipo di grafico, chiede al modello fino a 2 correzioni spiegando la forma richiesta.
    Solo alla fine, se serve, adatta il tipo di grafico ai dati (e lo segnala in "nota")."""
    titolo = str(g.get("titolo") or "Grafico")
    tipo_chiesto = g.get("tipo") if g.get("tipo") in llm.TIPI_GRAFICO else "table"
    tipo = tipo_chiesto
    sql = str(g.get("sql") or "")
    errore = ""
    tentativi = 3  # la query originale + fino a 2 correzioni del modello
    for tentativo in range(tentativi):
        ultimo = tentativo + 1 == tentativi
        try:
            sql = valida(sql)
            avviso = controlla_logica(sql)
            if avviso and not ultimo:
                raise SqlNonValida(avviso)
            ris = dati.esegui_query(sql, limite=1000)
            problema = _problema_forma(tipo, ris["colonne"], ris["tipi"], len(ris["righe"]))
            if problema and not ultimo:
                raise SqlNonValida(problema)
            errore = problema or ""
            break
        except Exception as ex:  # noqa: BLE001
            errore = str(ex) if isinstance(ex, SqlNonValida) else _errore_db(ex)
            if not ultimo:
                logger.info("Grafico '%s': correzione %d richiesta (%s)", titolo, tentativo + 1, errore)
                corr = llm.correggi_sql(
                    f"{richiesta}\nGrafico da correggere: '{titolo}', di tipo {tipo}.\n"
                    f"Forma dei dati richiesta: {_FORMA[tipo]}",
                    sql, errore, schema,
                )
                sql = corr["sql"]
    else:
        logger.warning("Grafico '%s' scartato: %s | SQL: %s", titolo, errore, sql)
        return {"titolo": titolo, "tipo": tipo, "errore": errore, "sql": sql}

    colonne, tipi, n = ris["colonne"], ris["tipi"], len(ris["righe"])
    if n == 0:
        return {"titolo": titolo, "tipo": tipo, "errore": "La query non restituisce righe.", "sql": sql}

    x = str(g.get("x") or "")
    y = _primo(colonne, tipi, str(g.get("y") or ""), {"numerico"})
    if tipo in ("bar", "pie", "line", "big_number") and not y:
        tipo = "table"  # nessuna colonna numerica da disegnare
    if tipo == "line":
        x = _primo(colonne, tipi, x, {"data"})
        if not x:
            tipo = "bar"
            x = str(g.get("x") or "")
    if tipo in ("bar", "pie"):
        x = _primo(colonne, tipi, x, {"testo", "data"})
        if not x:
            tipo = "big_number" if n == 1 else "table"
    if tipo == "big_number":
        x = ""
        if n > 1:
            tipo = "table"
    if tipo == "table":
        x, y = "", ""
    risultato = {
        "titolo": titolo,
        "tipo": tipo,
        "sql": sql,
        "x": x,
        "y": y,
        "colonne": colonne,
        "tipi": tipi,
        "righe": n,
    }
    if tipo != tipo_chiesto:
        risultato["nota"] = (
            f"mostrato come {tipo} invece di {tipo_chiesto}: dopo 2 correzioni i dati non hanno "
            f"ancora la forma adatta ({errore or 'forma non adatta'})"
        )
        logger.warning("Grafico '%s': %s | SQL: %s", titolo, risultato["nota"], sql)
    return risultato


# --------------------------------------------------------------------------- pagine

@ai_bp.route("/")
def pagina_assistant():
    if not current_user or not current_user.is_authenticated:
        return redirect("/login/?next=" + url_for("superset_ai.pagina_assistant"))
    return render_template(
        "superset_ai/assistant.html",
        modello=settings.OLLAMA_MODEL,
        ollama_url=settings.OLLAMA_URL,
        nome_database=settings.AI_DATABASE_NAME,
    )


# --------------------------------------------------------------------------- API

@ai_bp.route("/api/info")
@_richiede_login_api
def api_info():
    return jsonify(
        {
            "database_id": _id_database(),
            "database_nome": settings.AI_DATABASE_NAME,
            "schema": settings.AI_SCHEMA,
            "modello": settings.OLLAMA_MODEL,
            "ollama_url": settings.OLLAMA_URL,
        }
    )


@ai_bp.route("/api/stato")
@_richiede_login_api
def api_stato():
    risultato = llm.stato()
    try:
        dati.esegui_query("SELECT 1 AS ok", limite=1)
        risultato["database"] = "Database dei dati raggiungibile."
    except Exception as ex:  # noqa: BLE001
        risultato["ok"] = False
        risultato["database"] = f"Database dei dati non raggiungibile: {ex}"
    return jsonify(risultato)


@ai_bp.route("/api/schema")
@_richiede_login_api
def api_schema():
    try:
        return jsonify({"schema": dati.descrivi_schema(forza=request.args.get("aggiorna") == "1")})
    except Exception as ex:  # noqa: BLE001
        return _errore(f"Impossibile leggere lo schema: {ex}", 500)


@ai_bp.route("/api/sql", methods=["POST"])
@_richiede_login_api
def api_sql():
    corpo = request.get_json(silent=True) or {}
    domanda = str(corpo.get("domanda") or "").strip()
    if not domanda:
        return _errore("Scrivi una domanda.")
    try:
        risposta = _genera_ed_esegui(domanda, esegui=bool(corpo.get("esegui", True)))
    except llm.ErroreLLM as ex:
        return _errore(str(ex), 502)
    except Exception as ex:  # noqa: BLE001
        logger.exception("Errore Text-to-SQL")
        return _errore(f"Errore inatteso: {ex}", 500)
    return jsonify(risposta)


@ai_bp.route("/api/esegui", methods=["POST"])
@_richiede_login_api
def api_esegui():
    corpo = request.get_json(silent=True) or {}
    try:
        sql = valida(str(corpo.get("sql") or ""))
    except SqlNonValida as ex:
        return _errore(str(ex))
    try:
        return jsonify({"sql": sql, "risultato": dati.esegui_query(sql)})
    except Exception as ex:  # noqa: BLE001
        return _errore(f"Errore del database: {_errore_db(ex)}")


@ai_bp.route("/api/dashboard", methods=["POST"])
@_richiede_login_api
def api_dashboard():
    """Restituisce il PIANO della dashboard (grafici con SQL verificata).
    La creazione di dataset, grafici e dashboard la fa il browser con le REST API di
    Superset, cosi' rispetta i permessi dell'utente collegato."""
    corpo = request.get_json(silent=True) or {}
    richiesta = str(corpo.get("richiesta") or "").strip()
    if not richiesta:
        return _errore("Descrivi la dashboard che vuoi.")
    try:
        schema = dati.descrivi_schema()
        piano = llm.progetta_dashboard(richiesta, schema)
        grafici = [
            _verifica_grafico(g, richiesta, schema)
            for g in piano["grafici"][: settings.MAX_CHARTS]
            if isinstance(g, dict)
        ]
    except llm.ErroreLLM as ex:
        return _errore(str(ex), 502)
    except Exception as ex:  # noqa: BLE001
        logger.exception("Errore progettazione dashboard")
        return _errore(f"Errore inatteso: {ex}", 500)
    validi = [g for g in grafici if not g.get("errore")]
    scartati = [g for g in grafici if g.get("errore")]
    if not validi:
        return _errore(
            "Nessun grafico valido. Errori: " + "; ".join(f"{g['titolo']}: {g['errore']}" for g in scartati)
        )
    return jsonify(
        {
            "titolo": piano["titolo"],
            "grafici": validi,
            "scartati": scartati,
            "database_id": _id_database(),
            "schema": settings.AI_SCHEMA,
        }
    )


# --------------------------------------------------------------------------- aggancio a Superset

def app_mutator(app) -> None:
    """Chiamato da Superset all'avvio (FLASK_APP_MUTATOR).

    1. Mette i nostri template "override" davanti a quelli di Superset: cosi'
       tail_js_custom_extra.html (incluso in ogni pagina) carica il pannello per SQL Lab.
    2. Aggiunge la voce di menu "AI Assistant".
    """
    override = FileSystemLoader(os.path.join(_QUI, "templates", "override"))
    app.jinja_loader = ChoiceLoader([override, app.jinja_loader])

    try:
        from superset.extensions import appbuilder

        appbuilder.add_link(
            "AI Assistant",
            href="/ai/",
            icon="fa-magic",
            label="AI Assistant",
            category="AI",
            category_label="AI",
            category_icon="fa-magic",
        )
    except Exception:  # noqa: BLE001 - il menu e' un di piu': il pulsante flottante c'e' comunque
        logger.exception("Impossibile aggiungere la voce di menu AI Assistant")
