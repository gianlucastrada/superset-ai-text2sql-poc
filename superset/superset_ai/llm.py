"""Client Ollama e prompt per Text-to-SQL e progettazione di dashboard."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from . import settings


class ErroreLLM(RuntimeError):
    """Problema nel contattare il modello o nell'interpretarne la risposta."""


TIPI_GRAFICO = ["big_number", "bar", "line", "pie", "table"]

_SCHEMA_SQL = {
    "type": "object",
    "properties": {"sql": {"type": "string"}, "spiegazione": {"type": "string"}},
    "required": ["sql", "spiegazione"],
}

_SCHEMA_DASHBOARD = {
    "type": "object",
    "properties": {
        "titolo": {"type": "string"},
        "grafici": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titolo": {"type": "string"},
                    "tipo": {"type": "string", "enum": TIPI_GRAFICO},
                    "sql": {"type": "string"},
                    "x": {"type": "string"},
                    "y": {"type": "string"},
                },
                "required": ["titolo", "tipo", "sql", "x", "y"],
            },
        },
    },
    "required": ["titolo", "grafici"],
}

_REGOLE_SQL = """Regole per la SQL:
- Dialetto PostgreSQL. Una sola istruzione SELECT (eventualmente con WITH). Mai INSERT, UPDATE, DELETE, DDL, SET o piu' istruzioni.
- Usa SOLO tabelle e colonne presenti nello schema; non inventare nomi. Qualifica le colonne se usi JOIN.
- Se esiste una vista che contiene gia' i dati necessari (es. una vista di vendite con importi calcolati), preferiscila alle JOIN.
- Rispetta le indicazioni scritte nei commenti dello schema (ad esempio quali righe escludere da un totale).
- Alias delle colonne calcolate in minuscolo snake_case, senza spazi ne' accenti (es. fatturato_totale).
- Arrotonda importi e medie con ROUND(espressione::numeric, 2).
- Per classifiche usa ORDER BY ... DESC con LIMIT (10 se non indicato).
- Per andamenti nel tempo raggruppa per mese con date_trunc('month', <data>)::date AS mese e ordina per mese.
- I periodi relativi ("ultimo mese", "ultimo trimestre", "quest'anno") vanno calcolati rispetto all'ULTIMA data presente nei dati (indicata nello schema), non alla data di oggi.
- Per "ultimo mese", "ultimo trimestre", "ultimi 3 mesi", "ultimo semestre", "ultimo anno", "quest'anno" usa le date gia' calcolate nella sezione PERIODI DI RIFERIMENTO in fondo allo schema, scritte come costanti stringa. NON ricalcolarle con date_trunc, MAX() o CURRENT_DATE. I trimestri solari si usano solo se l'utente li nomina esplicitamente (es. "Q3", "terzo trimestre", "trimestre solare").
- Nella spiegazione indica sempre le date esatte del periodo considerato.
- Conteggio di ORDINI (numero di ordini, annullati, resi, per canale, per mese): usa la vista con una riga per ordine se esiste; altrimenti COUNT(DISTINCT ordine_id). Mai COUNT(*) su una vista o tabella con una riga per riga d'ordine: conterebbe le righe, non gli ordini.
- Percentuale di ordini in un certo stato: 100.0 * COUNT(*) FILTER (WHERE stato = '...') / COUNT(*) sulla vista con una riga per ordine.
- Se la domanda chiede un unico valore (totale, conteggio, media, percentuale) la query deve restituire UNA sola riga.
- Medie "per ordine", "per cliente", "per mese" ecc. richiedono DUE livelli: prima il totale per entita' in una sottoquery, poi la media dei totali. Esempio (media dell'importo totale per ordine):
  SELECT ROUND(AVG(totale)::numeric, 2) AS media_per_ordine FROM (SELECT ordine_id, SUM(importo) AS totale FROM tabella GROUP BY ordine_id) t
  SBAGLIATO: SELECT AVG(importo) FROM tabella GROUP BY ordine_id  (restituisce una riga per ordine, non la media).
- Ogni colonna usata in GROUP BY nella query finale deve comparire anche tra le colonne restituite.
- Se la domanda non indica un periodo, usa tutti i dati disponibili.
- Se la domanda e' ambigua scegli l'interpretazione piu' ragionevole e dichiarala nella spiegazione."""


def _prompt_sql(schema: str) -> str:
    return f"""Sei un esperto di PostgreSQL e di analisi dati. Trasformi domande in italiano in una query SQL di sola lettura.

{_REGOLE_SQL}

Rispondi SOLO con un oggetto JSON: {{"sql": "<query>", "spiegazione": "<una o due frasi in italiano su cosa calcola la query>"}}

SCHEMA DEL DATABASE:
{schema}"""


def _prompt_dashboard(schema: str, max_grafici: int) -> str:
    return f"""Sei un analista dati che progetta dashboard. Dalla richiesta dell'utente progetta una dashboard con da 3 a {max_grafici} grafici sui dati descritti dallo schema PostgreSQL. Per ogni grafico scrivi la query SQL che restituisce ESATTAMENTE i dati da disegnare, gia' aggregati.

Tipi di grafico ammessi e forma dei dati che la query deve restituire:
- "big_number": un indicatore chiave (KPI). 1 riga con 1 colonna numerica. y = nome di quella colonna, x = "".
- "bar": confronto tra categorie. 2 colonne: x = categoria (testo), y = valore numerico. Al massimo 15 righe, ordinate per y decrescente.
- "pie": composizione in percentuale. 2 colonne: x = categoria (testo), y = valore numerico. Al massimo 8 categorie.
- "line": andamento nel tempo. 2 colonne: x = data di tipo date (es. date_trunc('month', data)::date AS mese), y = valore numerico. Ordinata per x.
- "table": elenco di dettaglio. Piu' colonne, al massimo 50 righe. x = "" e y = "".

Metti prima 1-3 grafici "big_number" con i KPI principali, poi gli altri. Titoli brevi in italiano.
I grafici della stessa dashboard devono essere COERENTI tra loro: stessa definizione di ogni misura e stessi filtri (ad esempio, se il fatturato esclude gli ordini annullati, lo escludono TUTTI i grafici sul fatturato; la somma dell'andamento mensile deve coincidere con il KPI del totale nello stesso periodo).

{_REGOLE_SQL}

Rispondi SOLO con un oggetto JSON:
{{"titolo": "<titolo della dashboard>", "grafici": [{{"titolo": "...", "tipo": "big_number|bar|line|pie|table", "sql": "...", "x": "...", "y": "..."}}]}}

SCHEMA DEL DATABASE:
{schema}"""


def _estrai_json(testo: str) -> dict[str, Any]:
    testo = re.sub(r"<think>.*?</think>", "", testo or "", flags=re.DOTALL).strip()
    testo = re.sub(r"^```(?:json)?\s*|\s*```$", "", testo).strip()
    try:
        return json.loads(testo)
    except json.JSONDecodeError:
        inizio, fine = testo.find("{"), testo.rfind("}")
        if inizio >= 0 and fine > inizio:
            try:
                return json.loads(testo[inizio : fine + 1])
            except json.JSONDecodeError:
                pass
    raise ErroreLLM("Il modello non ha restituito un JSON valido: " + testo[:300])


def chat_json(sistema: str, utente: str, formato: dict[str, Any]) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": utente},
        ],
        "stream": False,
        "format": formato,
        "think": settings.OLLAMA_THINK,
        "options": {"temperature": 0.1},
    }
    if settings.OLLAMA_NUM_CTX > 0:
        corpo["options"]["num_ctx"] = settings.OLLAMA_NUM_CTX
    try:
        r = requests.post(
            f"{settings.OLLAMA_URL}/api/chat", json=corpo, timeout=settings.OLLAMA_TIMEOUT
        )
    except requests.Timeout as ex:
        raise ErroreLLM(
            f"Il modello non ha risposto entro {settings.OLLAMA_TIMEOUT} secondi."
        ) from ex
    except requests.RequestException as ex:
        raise ErroreLLM(f"Impossibile contattare Ollama su {settings.OLLAMA_URL}: {ex}") from ex
    if r.status_code >= 400:
        raise ErroreLLM(f"Ollama ha risposto {r.status_code}: {r.text[:300]}")
    try:
        contenuto = r.json().get("message", {}).get("content", "")
    except ValueError as ex:
        raise ErroreLLM("Risposta di Ollama non leggibile.") from ex
    return _estrai_json(contenuto)


def genera_sql(domanda: str, schema: str) -> dict[str, str]:
    dati = chat_json(_prompt_sql(schema), domanda, _SCHEMA_SQL)
    return {"sql": str(dati.get("sql", "")), "spiegazione": str(dati.get("spiegazione", ""))}


def correggi_sql(domanda: str, sql: str, errore: str, schema: str) -> dict[str, str]:
    richiesta = (
        f"Domanda originale: {domanda}\n\n"
        f"Questa query non e' accettabile o ha prodotto un errore:\n{sql}\n\n"
        f"Errore:\n{errore}\n\n"
        "Correggi la query rispettando lo schema. Cambia SOLO cio' che serve a risolvere l'errore: "
        "mantieni tutti i filtri e le condizioni della query originale (ad esempio l'esclusione "
        "degli ordini annullati) e tutte le regole indicate nei commenti dello schema."
    )
    dati = chat_json(_prompt_sql(schema), richiesta, _SCHEMA_SQL)
    return {"sql": str(dati.get("sql", "")), "spiegazione": str(dati.get("spiegazione", ""))}


def progetta_dashboard(richiesta: str, schema: str) -> dict[str, Any]:
    dati = chat_json(
        _prompt_dashboard(schema, settings.MAX_CHARTS), richiesta, _SCHEMA_DASHBOARD
    )
    grafici = dati.get("grafici") or []
    if not isinstance(grafici, list):
        grafici = []
    return {"titolo": str(dati.get("titolo") or "Dashboard AI"), "grafici": grafici}


def stato() -> dict[str, Any]:
    """Verifica che Ollama risponda e che il modello sia presente."""
    try:
        r = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=10)
        r.raise_for_status()
        modelli = [m.get("name") for m in r.json().get("models", [])]
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "messaggio": f"Ollama non raggiungibile su {settings.OLLAMA_URL}: {ex}"}
    presente = settings.OLLAMA_MODEL in modelli
    return {
        "ok": presente,
        "messaggio": (
            f"Ollama raggiungibile, modello {settings.OLLAMA_MODEL} presente."
            if presente
            else f"Ollama raggiungibile ma il modello {settings.OLLAMA_MODEL} non c'e'. Disponibili: {', '.join(modelli)}"
        ),
        "modelli": modelli,
    }
