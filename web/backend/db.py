"""Capa de persistencia SQLite (stdlib) del backend de zipzi.

Tablas:
  - profiles: perfiles (seed sintético desde perfiles.csv + seed_display.json,
    más los perfiles que crea el usuario con es_usuario=1).
  - connections: acciones connect/save entre perfiles (idempotentes por
    UNIQUE(from_id, to_id, action)).

El seedeo corre solo si la tabla profiles está vacía.
"""

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone

_AQUI = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(_AQUI))
DEFAULT_DB = os.path.join(_AQUI, "zipzi.db")
RUTA_CSV = os.path.join(REPO_ROOT, "perfiles.csv")
RUTA_SEED_DISPLAY = os.path.join(_AQUI, "seed_display.json")

# Columnas que se guardan como JSON (TEXT) en SQLite.
JSON_COLS = {
    "orientacion", "rubro", "skills_ofrece", "skills_busca",
    "intereses", "objetivos_lista", "proyectos_lista",
}

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    orientacion TEXT,
    objetivo TEXT,
    rubro TEXT,
    horas_semana INTEGER,
    horizonte_meses INTEGER,
    idioma TEXT,
    timezone TEXT,
    apetito_riesgo INTEGER,
    estilo_decision INTEGER,
    confianza INTEGER,
    energia INTEGER,
    disciplina INTEGER,
    creatividad INTEGER,
    skills_ofrece TEXT,
    skills_busca TEXT,
    inversion_dinero INTEGER,
    edad INTEGER,
    ciudad TEXT,
    tagline TEXT,
    bio TEXT,
    vision TEXT,
    intereses TEXT,
    objetivos_lista TEXT,
    proyectos_lista TEXT,
    quien_busco TEXT,
    disponibilidad TEXT,
    es_usuario INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('connect', 'save')),
    created_at TEXT,
    UNIQUE(from_id, to_id, action)
);
"""

_COLUMNAS_PROFILE = [
    "nombre", "orientacion", "objetivo", "rubro", "horas_semana",
    "horizonte_meses", "idioma", "timezone", "apetito_riesgo",
    "estilo_decision", "confianza", "energia", "disciplina", "creatividad",
    "skills_ofrece", "skills_busca", "inversion_dinero", "edad", "ciudad",
    "tagline", "bio", "vision", "intereses", "objetivos_lista",
    "proyectos_lista", "quien_busco", "disponibilidad", "es_usuario",
    "created_at",
]


def db_path():
    """Path del SQLite: env ZIPZI_DB o default junto a este módulo."""
    return os.environ.get("ZIPZI_DB", DEFAULT_DB)


def disponibilidad_desde_horas(horas_semana):
    hs = int(horas_semana)
    if hs >= 20:
        return "Disponible"
    if hs >= 10:
        return "Selectivo"
    return "Ocupado"


def get_connection(path=None):
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    return conn


def profile_from_row(row):
    """Convierte una fila sqlite3.Row en dict con las listas ya parseadas."""
    perfil = dict(row)
    for col in JSON_COLS:
        raw = perfil.get(col)
        if raw is None:
            perfil[col] = []
        elif isinstance(raw, str):
            try:
                perfil[col] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                perfil[col] = []
    return perfil


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _seed(conn):
    """Puebla profiles desde perfiles.csv + seed_display.json (datos sintéticos)."""
    with open(RUTA_CSV, "r", encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))
    with open(RUTA_SEED_DISPLAY, "r", encoding="utf-8") as f:
        display = json.load(f)["profiles"]

    ahora = _ahora()
    for fila in filas:
        nombre = fila["id"]
        if nombre not in display:
            raise ValueError(f"seed_display.json no tiene display para '{nombre}'")
        d = display[nombre]
        valores = {
            "nombre": nombre,
            "orientacion": fila["orientacion"],
            "objetivo": fila["objetivo"],
            "rubro": fila["rubro"],
            "horas_semana": int(fila["horas_semana"]),
            "horizonte_meses": int(fila["horizonte_meses"]),
            "idioma": fila["idioma"],
            "timezone": fila["timezone"],
            "apetito_riesgo": int(fila["apetito_riesgo"]),
            "estilo_decision": int(fila["estilo_decision"]),
            "confianza": 3,   # neutro: el CSV no trae rasgos sociales
            "energia": 3,
            "disciplina": 3,
            "creatividad": 3,
            "skills_ofrece": fila["skills_ofrece"],
            "skills_busca": fila["skills_busca"],
            "inversion_dinero": int(fila["inversion_dinero"]),
            "edad": d["edad"],
            "ciudad": d["ciudad"],
            "tagline": d["tagline"],
            "bio": d["bio"],
            "vision": d["vision"],
            "intereses": json.dumps(d["intereses"], ensure_ascii=False),
            "objetivos_lista": json.dumps(d["objetivos_lista"], ensure_ascii=False),
            "proyectos_lista": json.dumps(d["proyectos_lista"], ensure_ascii=False),
            "quien_busco": d["quien_busco"],
            "disponibilidad": disponibilidad_desde_horas(fila["horas_semana"]),
            "es_usuario": 0,
            "created_at": ahora,
        }
        columnas = ", ".join(_COLUMNAS_PROFILE)
        placeholders = ", ".join("?" for _ in _COLUMNAS_PROFILE)
        conn.execute(
            f"INSERT INTO profiles ({columnas}) VALUES ({placeholders})",
            [valores[c] for c in _COLUMNAS_PROFILE],
        )


def init_db(path=None):
    """Crea tablas y seedea si profiles está vacía. Idempotente."""
    conn = get_connection(path)
    try:
        conn.executescript(_ESQUEMA)
        n = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        if n == 0:
            _seed(conn)
            conn.commit()
    finally:
        conn.close()


# ---------- Acceso a profiles ----------

def fetch_all_profiles(conn):
    return [profile_from_row(r) for r in conn.execute("SELECT * FROM profiles ORDER BY id")]


def fetch_profile(conn, profile_id):
    row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return profile_from_row(row) if row else None


def fetch_profile_by_nombre(conn, nombre):
    row = conn.execute("SELECT * FROM profiles WHERE nombre = ?", (nombre,)).fetchone()
    return profile_from_row(row) if row else None


def insert_profile(conn, datos):
    """datos: dict con las claves de _COLUMNAS_PROFILE (listas como listas Python)."""
    fila = {}
    for col in _COLUMNAS_PROFILE:
        v = datos.get(col)
        if col in JSON_COLS and isinstance(v, (list, tuple)):
            v = json.dumps(list(v), ensure_ascii=False)
        fila[col] = v
    columnas = ", ".join(_COLUMNAS_PROFILE)
    placeholders = ", ".join("?" for _ in _COLUMNAS_PROFILE)
    cur = conn.execute(
        f"INSERT INTO profiles ({columnas}) VALUES ({placeholders})",
        [fila[c] for c in _COLUMNAS_PROFILE],
    )
    conn.commit()
    return fetch_profile(conn, cur.lastrowid)


# ---------- Acceso a connections ----------

def fetch_connection(conn, from_id, to_id, action):
    row = conn.execute(
        "SELECT * FROM connections WHERE from_id = ? AND to_id = ? AND action = ?",
        (from_id, to_id, action),
    ).fetchone()
    return dict(row) if row else None


def fetch_connection_by_id(conn, connection_id):
    row = conn.execute("SELECT * FROM connections WHERE id = ?", (connection_id,)).fetchone()
    return dict(row) if row else None


def insert_connection(conn, from_id, to_id, action):
    cur = conn.execute(
        "INSERT INTO connections (from_id, to_id, action, created_at) VALUES (?, ?, ?, ?)",
        (from_id, to_id, action, _ahora()),
    )
    conn.commit()
    return fetch_connection_by_id(conn, cur.lastrowid)


def fetch_connections_from(conn, profile_id):
    rows = conn.execute(
        "SELECT * FROM connections WHERE from_id = ? ORDER BY id", (profile_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def delete_connection(conn, connection_id):
    cur = conn.execute("DELETE FROM connections WHERE id = ?", (connection_id,))
    conn.commit()
    return cur.rowcount > 0
