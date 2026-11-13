"""Accesso al database dei dati: esecuzione delle query e descrizione dello schema per il modello."""

from __future__ import annotations

import datetime as dt
import decimal
import threading
import time
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from . import settings

_engine: Engine | None = None
_lock = threading.Lock()
_schema_cache: dict[str, Any] = {"testo": None, "quando": 0.0, "dove": {}}

# OID dei tipi Postgres, per capire se una colonna e' numerica o temporale
_OID_NUMERICI = {20, 21, 23, 26, 700, 701, 790, 1700}
_OID_TEMPORALI = {1082, 1114, 1184}


def engine() -> Engine:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                if not settings.AI_DATA_URI:
                    raise RuntimeError("Variabile AI_DATA_URI non impostata.")
                _engine = create_engine(
                    settings.AI_DATA_URI, pool_pre_ping=True, pool_size=3, max_overflow=2
                )
    return _engine


def _json(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return str(v)
    if isinstance(v, (bytes, memoryview)):
        return "<binario>"
    return v


def _tipo(type_code: int) -> str:
    if type_code in _OID_NUMERICI:
        return "numerico"
    if type_code in _OID_TEMPORALI:
        return "data"
    return "testo"


def _esegui(sql: str, params: tuple | None = None) -> tuple[list, list]:
    """Esegue in una transazione di sola lettura, sempre annullata alla fine."""
    raw = engine().raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("SET TRANSACTION READ ONLY")
        if params is None:
            cur.execute(sql)  # niente parametri: psycopg2 non interpreta i '%'
        else:
            cur.execute(sql, params)
        descr = list(cur.description or [])
        righe = cur.fetchall() if cur.description else []
        return descr, righe
    finally:
        try:
            raw.rollback()
        finally:
            raw.close()


def esegui_query(sql: str, limite: int | None = None) -> dict[str, Any]:
    """Esegue una SELECT (gia' validata) e restituisce colonne, tipi e righe (max `limite`)."""
    limite = limite or settings.MAX_PREVIEW_ROWS
    avvolta = f"SELECT * FROM (\n{sql}\n) AS ai_q LIMIT {int(limite) + 1}"
    inizio = time.monotonic()
    descr, righe = _esegui(avvolta)
    ms = int((time.monotonic() - inizio) * 1000)
    troncato = len(righe) > limite
    righe = righe[:limite]
    return {
        "colonne": [d[0] for d in descr],
        "tipi": [_tipo(d[1]) for d in descr],
        "righe": [[_json(v) for v in r] for r in righe],
        "troncato": troncato,
        "ms": ms,
    }


_SQL_COLONNE = """
SELECT c.table_name, t.table_type, c.column_name, c.data_type,
       col_description((quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                       c.ordinal_position) AS commento_colonna,
       obj_description((quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                       'pg_class') AS commento_tabella
FROM information_schema.columns c
JOIN information_schema.tables t
  ON t.table_schema = c.table_schema AND t.table_name = c.table_name
WHERE c.table_schema = %s
ORDER BY t.table_type, c.table_name, c.ordinal_position
"""

_SQL_RELAZIONI = """
SELECT con.conrelid::regclass::text, a.attname, con.confrelid::regclass::text, af.attname
FROM pg_constraint con
JOIN pg_attribute a  ON a.attrelid = con.conrelid  AND a.attnum = con.conkey[1]
JOIN pg_attribute af ON af.attrelid = con.confrelid AND af.attnum = con.confkey[1]
WHERE con.contype = 'f' AND con.connamespace = %s::regnamespace
ORDER BY 1, 2
"""

_SQL_RIGHE = """
SELECT c.relname, c.reltuples::bigint
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind = 'r'
"""


def _inizio_mese(d: dt.date, mesi_indietro: int) -> dt.date:
    """Primo giorno del mese spostato di N mesi indietro (N negativo = in avanti)."""
    totale = d.year * 12 + (d.month - 1) - mesi_indietro
    return dt.date(totale // 12, totale % 12 + 1, 1)


def periodi_riferimento(ultima: dt.date, colonna: str) -> list[str]:
    """Periodi relativi gia' calcolati: il modello li copia come costanti invece di
    ricavarli con date_trunc (dove tende a scegliere interpretazioni diverse)."""
    inizio_trim = dt.date(ultima.year, 3 * ((ultima.month - 1) // 3) + 1, 1)
    fine_trim = _inizio_mese(inizio_trim, -3) - dt.timedelta(days=1)
    if ultima == fine_trim:
        # i dati arrivano all'ultimo giorno del trimestre: e' gia' completo
        inizio_trim_prec, fine_trim_prec = inizio_trim, fine_trim
    else:
        inizio_trim_prec = _inizio_mese(inizio_trim, 3)
        fine_trim_prec = inizio_trim - dt.timedelta(days=1)

    def p(nome: str, da: dt.date, a: dt.date) -> str:
        return f"  - {nome}: dal '{da.isoformat()}' al '{a.isoformat()}'"

    return [
        f"PERIODI DI RIFERIMENTO (ultima data presente nei dati: '{ultima.isoformat()}', colonna {colonna}).",
        "Per i periodi relativi usa ESATTAMENTE queste date come costanti, es. BETWEEN 'aaaa-mm-gg' AND 'aaaa-mm-gg':",
        p("ultimo mese", _inizio_mese(ultima, 0), ultima),
        p("ultimo trimestre / ultimi 3 mesi", _inizio_mese(ultima, 2), ultima),
        p("ultimo semestre / ultimi 6 mesi", _inizio_mese(ultima, 5), ultima),
        p("ultimo anno / ultimi 12 mesi", _inizio_mese(ultima, 11), ultima),
        p("anno in corso (quest'anno)", dt.date(ultima.year, 1, 1), ultima),
        p("anno precedente", dt.date(ultima.year - 1, 1, 1), dt.date(ultima.year - 1, 12, 31)),
        p("trimestre solare in corso (solo se richiesto esplicitamente)", inizio_trim, ultima),
        p("ultimo trimestre solare completo (solo se richiesto esplicitamente)", inizio_trim_prec, fine_trim_prec),
    ]


def _qi(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def descrivi_schema(forza: bool = False) -> str:
    """Testo compatto che descrive tabelle, colonne, commenti, valori tipici e relazioni."""
    adesso = time.time()
    if (
        not forza
        and _schema_cache["testo"]
        and adesso - _schema_cache["quando"] < settings.SCHEMA_CACHE_SECONDS
    ):
        return _schema_cache["testo"]

    schema = settings.AI_SCHEMA
    _, colonne = _esegui(_SQL_COLONNE, (schema,))
    _, relazioni = _esegui(_SQL_RELAZIONI, (schema,))
    _, conteggi = _esegui(_SQL_RIGHE, (schema,))
    righe_per_tabella = {nome: n for nome, n in conteggi}

    tabelle: dict[str, dict[str, Any]] = {}
    dove: dict[str, list[str]] = {}  # colonna -> tabelle/viste che la contengono
    for tabella, tipo_t, colonna, tipo_c, comm_col, comm_tab in colonne:
        t = tabelle.setdefault(
            tabella, {"vista": tipo_t == "VIEW", "commento": comm_tab, "colonne": []}
        )
        t["colonne"].append((colonna, tipo_c, comm_col))
        dove.setdefault(colonna.lower(), []).append(f"{schema}.{tabella}")

    righe_testo: list[str] = []
    ultima: tuple[dt.date, str] | None = None  # data piu' recente nei dati e colonna di provenienza
    for tabella, info in tabelle.items():
        intest = ("VISTA " if info["vista"] else "TABELLA ") + f"{schema}.{tabella}"
        if not info["vista"] and righe_per_tabella.get(tabella, -1) >= 0:
            intest += f" (circa {righe_per_tabella[tabella]} righe)"
        if info["commento"]:
            intest += f" -- {info['commento']}"
        righe_testo.append(intest)
        for colonna, tipo_c, comm_col in info["colonne"]:
            riga = f"  - {colonna} {tipo_c}"
            if comm_col:
                riga += f" -- {comm_col}"
            # Valori tipici per colonne di testo con pochi valori distinti (solo tabelle)
            if not info["vista"] and tipo_c in ("text", "character varying", "character"):
                try:
                    _, valori = _esegui(
                        f"SELECT DISTINCT {_qi(colonna)} FROM {_qi(schema)}.{_qi(tabella)} "
                        f"WHERE {_qi(colonna)} IS NOT NULL LIMIT 16"
                    )
                    if 0 < len(valori) <= 15:
                        riga += " [valori: " + ", ".join(sorted(str(v[0]) for v in valori)) + "]"
                except Exception:  # noqa: BLE001
                    pass
            # Intervallo per le date (solo tabelle)
            if not info["vista"] and tipo_c in ("date", "timestamp without time zone", "timestamp with time zone"):
                try:
                    _, mm = _esegui(
                        f"SELECT min({_qi(colonna)}), max({_qi(colonna)}) FROM {_qi(schema)}.{_qi(tabella)}"
                    )
                    if mm and mm[0][0] is not None:
                        riga += f" [dal {_json(mm[0][0])} al {_json(mm[0][1])}]"
                        massimo = mm[0][1]
                        if isinstance(massimo, dt.datetime):
                            massimo = massimo.date()
                        if ultima is None or massimo > ultima[0]:
                            ultima = (massimo, f"{tabella}.{colonna}")
                except Exception:  # noqa: BLE001
                    pass
            righe_testo.append(riga)
        righe_testo.append("")

    if relazioni:
        righe_testo.append("RELAZIONI (chiavi esterne):")
        for da_t, da_c, a_t, a_c in relazioni:
            righe_testo.append(f"  - {da_t}.{da_c} -> {a_t}.{a_c}")

    if ultima:
        righe_testo.append("")
        righe_testo.extend(periodi_riferimento(*ultima))

    testo = "\n".join(righe_testo).strip()
    _schema_cache.update(testo=testo, quando=adesso, dove=dove)
    return testo


def dove_si_trova(colonna: str) -> list[str]:
    """Tabelle/viste dello schema che contengono la colonna (per aiutare il modello a correggersi)."""
    descrivi_schema()  # usa la cache se valida
    return list(_schema_cache["dove"].get(colonna.lower(), []))
