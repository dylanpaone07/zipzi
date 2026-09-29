"""API FastAPI del MVP web de zipzi.

Rutas /api/* (JSON) + el frontend estático servido desde / (montado DESPUÉS
de las rutas /api, el orden importa: si no, StaticFiles se comería /api).
"""

import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

_AQUI = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(_AQUI))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from matching import NECESIDADES_POR_OBJETIVO  # noqa: E402

from . import db  # noqa: E402
from .desglose import desglose_match  # noqa: E402

StrList = Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1, max_length=12)]
StrListCorta = Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1, max_length=5)]
Escala = Annotated[int, Field(ge=1, le=5)]


class ProfileCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    edad: int = Field(ge=16, le=100)
    ciudad: str = Field(min_length=1, max_length=60)
    idioma: str = Field(min_length=1, max_length=10)
    timezone: str = Field(pattern=r"^GMT[+-]\d+$")
    horas_semana: int = Field(ge=1, le=80)
    horizonte_meses: int = Field(ge=1, le=120)
    objetivo: str
    orientacion: StrList
    rubro: StrList
    skills_ofrece: StrList
    skills_busca: StrList
    intereses: StrList
    apetito_riesgo: Escala
    estilo_decision: Escala
    confianza: Escala
    energia: Escala
    disciplina: Escala
    creatividad: Escala
    inversion_dinero: Escala
    bio: str = Field(min_length=1, max_length=500)
    vision: str = Field(min_length=1, max_length=500)
    tagline: str = Field(min_length=1, max_length=140)
    quien_busco: str = Field(min_length=1, max_length=300)
    objetivos_lista: StrListCorta
    proyectos_lista: StrListCorta

    @field_validator("objetivo")
    @classmethod
    def objetivo_conocido(cls, v):
        if v not in NECESIDADES_POR_OBJETIVO:
            raise ValueError(
                f"objetivo desconocido; valores válidos: {sorted(NECESIDADES_POR_OBJETIVO)}"
            )
        return v


class ConnectionCreate(BaseModel):
    from_id: int
    to_id: int
    action: Literal["connect", "save"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()  # crea tablas + seedea solo si profiles está vacía
    yield


app = FastAPI(title="zipzi API", lifespan=lifespan)


def get_conn():
    conn = db.get_connection()
    try:
        yield conn
    finally:
        conn.close()


ConnDep = Annotated[object, Depends(get_conn)]


# ---------- Serializadores ----------

def profile_summary(p):
    return {
        "id": p["id"],
        "nombre": p["nombre"],
        "edad": p["edad"],
        "ciudad": p["ciudad"],
        "tagline": p["tagline"],
        "bio": p["bio"],
        "disponibilidad": p["disponibilidad"],
        "skills_ofrece": p["skills_ofrece"],
        "intereses": p["intereses"],
    }


def profile_detail(p):
    base = profile_summary(p)
    base.update({
        "vision": p["vision"],
        "objetivo": p["objetivo"],
        "rubro": p["rubro"],
        "orientacion": p["orientacion"],
        "idioma": p["idioma"],
        "timezone": p["timezone"],
        "horas_semana": p["horas_semana"],
        "horizonte_meses": p["horizonte_meses"],
        "rasgos": {
            "apetito_riesgo": p["apetito_riesgo"],
            "estilo_decision": p["estilo_decision"],
            "confianza": p["confianza"],
            "energia": p["energia"],
            "disciplina": p["disciplina"],
            "creatividad": p["creatividad"],
        },
        "inversion_dinero": p["inversion_dinero"],
        "objetivos_lista": p["objetivos_lista"],
        "proyectos_lista": p["proyectos_lista"],
        "quien_busco": p["quien_busco"],
        "es_usuario": bool(p["es_usuario"]),
    })
    return base


def connection_out(c):
    return {
        "id": c["id"],
        "from_id": c["from_id"],
        "to_id": c["to_id"],
        "action": c["action"],
        "created_at": c["created_at"],
    }


def _get_profile_or_404(conn, profile_id):
    p = db.fetch_profile(conn, profile_id)
    if p is None:
        raise HTTPException(status_code=404, detail="perfil no encontrado")
    return p


# ---------- Profiles ----------

@app.get("/api/profiles")
def listar_profiles(
    conn: ConnDep,
    q: str | None = Query(default=None),
    disponibilidad: str | None = Query(default=None),
    habilidad: str | None = Query(default=None),
    interes: str | None = Query(default=None),
):
    perfiles = db.fetch_all_profiles(conn)
    qq = q.lower() if q else None
    hab = habilidad.lower() if habilidad else None
    inter = interes.lower() if interes else None

    def ok(p):
        if disponibilidad and p["disponibilidad"] != disponibilidad:
            return False
        if hab and not any(hab == s.lower() for s in p["skills_ofrece"] + p["skills_busca"]):
            return False
        if inter and not any(inter == s.lower() for s in p["intereses"]):
            return False
        if qq:
            campos = [p["nombre"], p["bio"], p["vision"], p["tagline"], p["objetivo"]]
            campos += p["skills_ofrece"] + p["skills_busca"] + p["intereses"] + p["proyectos_lista"]
            if not any(qq in str(c).lower() for c in campos if c):
                return False
        return True

    return [profile_summary(p) for p in perfiles if ok(p)]


@app.get("/api/profiles/{profile_id}")
def detalle_profile(profile_id: int, conn: ConnDep):
    return profile_detail(_get_profile_or_404(conn, profile_id))


@app.post("/api/profiles")
def crear_profile(body: ProfileCreate, conn: ConnDep):
    if db.fetch_profile_by_nombre(conn, body.nombre) is not None:
        raise HTTPException(status_code=409, detail="ya existe un perfil con ese nombre")
    datos = body.model_dump()
    datos["disponibilidad"] = db.disponibilidad_desde_horas(datos["horas_semana"])
    datos["es_usuario"] = 1
    datos["created_at"] = db._ahora()
    creado = db.insert_profile(conn, datos)
    return profile_detail(creado)


# ---------- Meta ----------

@app.get("/api/meta")
def meta(conn: ConnDep):
    perfiles = db.fetch_all_profiles(conn)
    return {
        "objetivos": sorted(NECESIDADES_POR_OBJETIVO.keys()),
        "idiomas": sorted({p["idioma"] for p in perfiles if p["idioma"]}),
        "timezones": sorted({p["timezone"] for p in perfiles if p["timezone"]}),
        "orientaciones": sorted({o for p in perfiles for o in p["orientacion"]}),
        "rubros": sorted({r for p in perfiles for r in p["rubro"]}),
        "skills": sorted({s for p in perfiles for s in p["skills_ofrece"] + p["skills_busca"]}),
        "intereses": sorted({i for p in perfiles for i in p["intereses"]}),
        "disponibilidades": sorted({p["disponibilidad"] for p in perfiles if p["disponibilidad"]}),
    }


# ---------- Matches ----------

@app.get("/api/matches")
def matches(profile_id: int, conn: ConnDep):
    yo = _get_profile_or_404(conn, profile_id)
    items = []
    for otro in db.fetch_all_profiles(conn):
        if otro["id"] == profile_id:
            continue
        d = desglose_match(yo, otro)
        items.append({
            "profile": profile_summary(otro),
            "pasa_filtros": d["pasa_filtros"],
            "motivo_descarte": d["motivo_descarte"],
            "total": d["total"],
            "compatibilidad_personal": d["compatibilidad_personal"],
            "necesidad": d["necesidad"],
            "desglose": {
                "personal_traits": d["personal_traits"],
                "necesidad_traits": d["necesidad_traits"],
            },
            "similitud_objetivos_pct": d["similitud_objetivos_pct"],
            "similitud_objetivos_categoria": d["similitud_objetivos_categoria"],
            "ajuste_objetivo": d["ajuste_objetivo"],
        })
    # Primero los que pasan los filtros, luego por total descendente.
    items.sort(key=lambda x: (not x["pasa_filtros"], -x["total"]))
    return items


# ---------- Connections ----------

@app.post("/api/connections")
def crear_connection(body: ConnectionCreate, conn: ConnDep):
    if body.from_id == body.to_id:
        raise HTTPException(status_code=422, detail="from_id y to_id no pueden ser iguales")
    _get_profile_or_404(conn, body.from_id)
    _get_profile_or_404(conn, body.to_id)
    existente = db.fetch_connection(conn, body.from_id, body.to_id, body.action)
    if existente is not None:
        return connection_out(existente)  # idempotente
    creada = db.insert_connection(conn, body.from_id, body.to_id, body.action)
    return connection_out(creada)


@app.get("/api/connections")
def listar_connections(profile_id: int, conn: ConnDep):
    _get_profile_or_404(conn, profile_id)
    items = []
    for c in db.fetch_connections_from(conn, profile_id):
        destino = db.fetch_profile(conn, c["to_id"])
        items.append({
            "id": c["id"],
            "action": c["action"],
            "created_at": c["created_at"],
            "profile": profile_summary(destino) if destino else None,
        })
    return items


@app.delete("/api/connections/{connection_id}")
def borrar_connection(connection_id: int, conn: ConnDep):
    if not db.delete_connection(conn, connection_id):
        raise HTTPException(status_code=404, detail="connection no encontrada")
    return {"ok": True}


# ---------- Frontend estático ----------
# Se monta DESPUÉS de todas las rutas /api (el orden importa): si no existe
# el directorio web/frontend todavía, no se monta y la API sigue andando.
_FRONTEND_DIR = os.path.join(REPO_ROOT, "web", "frontend")
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
