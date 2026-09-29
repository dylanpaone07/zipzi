"""Tests de la API de zipzi (FastAPI).

OJO: ZIPZI_DB se setea a un tmp dir ANTES de importar la app, para no tocar
la base real. El TestClient corre el lifespan -> init_db() -> seed sintético.
"""

import os
import sys
import tempfile

import pytest

_AQUI = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(_AQUI))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ["ZIPZI_DB"] = os.path.join(tempfile.mkdtemp(prefix="zipzi_test_"), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from web.backend.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _payload(nombre="Test Uno"):
    return {
        "nombre": nombre,
        "edad": 26,
        "ciudad": "Buenos Aires",
        "idioma": "es",
        "timezone": "GMT-3",
        "horas_semana": 25,
        "horizonte_meses": 12,
        "objetivo": "startup_tech",
        "orientacion": ["it", "producto"],
        "rubro": ["fintech"],
        "skills_ofrece": ["backend", "python"],
        "skills_busca": ["ventas"],
        "intereses": ["open source", "café"],
        "apetito_riesgo": 4,
        "estilo_decision": 3,
        "confianza": 3,
        "energia": 4,
        "disciplina": 3,
        "creatividad": 4,
        "inversion_dinero": 2,
        "bio": "Dev que quiere armar algo propio.",
        "vision": "Un producto que la gente ame.",
        "tagline": "Codeo y aprendo.",
        "quien_busco": "Alguien que venda.",
        "objetivos_lista": ["Lanzar MVP"],
        "proyectos_lista": ["Side project"],
    }


def _mateo_id(client):
    r = client.get("/api/profiles", params={"q": "Mateo Rossi"})
    assert r.status_code == 200 and r.json()
    return r.json()[0]["id"]


# ---------- POST /api/profiles ----------

def test_crear_perfil_ok(client):
    r = client.post("/api/profiles", json=_payload("Test Uno"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["nombre"] == "Test Uno"
    assert body["es_usuario"] is True
    assert body["disponibilidad"] == "Disponible"  # 25h -> Disponible
    assert body["rasgos"]["apetito_riesgo"] == 4
    assert isinstance(body["id"], int)


def test_crear_perfil_422_escala_invalida(client):
    p = _payload("Test Escala")
    p["apetito_riesgo"] = 9
    r = client.post("/api/profiles", json=p)
    assert r.status_code == 422, r.text


def test_crear_perfil_422_timezone_invalido(client):
    p = _payload("Test TZ")
    p["timezone"] = "UTC-3"
    r = client.post("/api/profiles", json=p)
    assert r.status_code == 422, r.text


def test_crear_perfil_409_nombre_duplicado(client):
    r = client.post("/api/profiles", json=_payload("Test Uno"))
    assert r.status_code == 409, r.text


# ---------- GET /api/matches ----------

def test_matches_con_desglose_completo(client):
    mid = _mateo_id(client)
    r = client.get("/api/matches", params={"profile_id": mid})
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) >= 14  # todos menos él mismo
    primero = items[0]
    for clave in ("profile", "pasa_filtros", "motivo_descarte", "total",
                  "compatibilidad_personal", "necesidad", "desglose",
                  "similitud_objetivos_pct", "similitud_objetivos_categoria",
                  "ajuste_objetivo"):
        assert clave in primero, f"falta {clave}"
    d = primero["desglose"]
    assert len(d["personal_traits"]) == 7
    assert len(d["necesidad_traits"]) == 4
    for t in d["personal_traits"] + d["necesidad_traits"]:
        assert set(t) == {"key", "label", "coincidencia", "peso"}
        assert 0.0 <= t["coincidencia"] <= 1.0
        assert t["peso"] > 0
    assert sum(t["peso"] for t in d["personal_traits"]) == pytest.approx(1.0)
    assert sum(t["peso"] for t in d["necesidad_traits"]) == pytest.approx(1.0)
    # Orden: primero los que pasan filtros, luego total desc.
    vistos_filtrados = False
    anterior_total = None
    for it in items:
        if not it["pasa_filtros"]:
            vistos_filtrados = True
            anterior_total = None
        else:
            assert not vistos_filtrados, "un pasa_filtros=True aparece después de un False"
            if anterior_total is not None:
                assert it["total"] <= anterior_total + 1e-9
            anterior_total = it["total"]
    # Filtro duro conocido: Mateo (es) vs Elena (en) -> idioma.
    elena = next(i for i in items if i["profile"]["nombre"] == "Elena Rostova")
    assert elena["pasa_filtros"] is False
    assert elena["motivo_descarte"] == "idioma"
    # Similitud de objetivos coherente.
    assert primero["similitud_objetivos_categoria"] in ("positiva", "neutral", "negativa")
    assert isinstance(primero["similitud_objetivos_pct"], int)


def test_matches_404(client):
    r = client.get("/api/matches", params={"profile_id": 999999})
    assert r.status_code == 404


# ---------- GET /api/profiles (filtros) ----------

def test_filtro_q(client):
    r = client.get("/api/profiles", params={"q": "python"})
    assert r.status_code == 200
    nombres = [p["nombre"] for p in r.json()]
    assert "Mateo Rossi" in nombres


def test_filtro_disponibilidad(client):
    r = client.get("/api/profiles", params={"disponibilidad": "Disponible"})
    assert r.status_code == 200
    assert r.json()
    assert all(p["disponibilidad"] == "Disponible" for p in r.json())
    nombres = [p["nombre"] for p in r.json()]
    assert "Mateo Rossi" in nombres and "Valentina Méndez" not in nombres


def test_filtro_habilidad(client):
    r = client.get("/api/profiles", params={"habilidad": "python"})
    assert r.status_code == 200
    nombres = [p["nombre"] for p in r.json()]
    assert "Mateo Rossi" in nombres  # lo ofrece
    r2 = client.get("/api/profiles", params={"habilidad": "ventas"})
    nombres2 = [p["nombre"] for p in r2.json()]
    assert "Mateo Rossi" in nombres2  # lo busca


def test_filtro_interes(client):
    r = client.get("/api/profiles", params={"interes": "ajedrez"})
    assert r.status_code == 200
    nombres = [p["nombre"] for p in r.json()]
    assert nombres == ["Elena Rostova"]


def test_profile_404(client):
    assert client.get("/api/profiles/999999").status_code == 404


# ---------- Connections ----------

def test_connections_flujo(client):
    # Perfil usuario para el flujo (from_id).
    r = client.post("/api/profiles", json=_payload("Conn Test A"))
    assert r.status_code == 200
    a_id = r.json()["id"]
    mid = _mateo_id(client)

    # Crear connect + save.
    rc = client.post("/api/connections", json={"from_id": a_id, "to_id": mid, "action": "connect"})
    assert rc.status_code == 200, rc.text
    conn_id = rc.json()["id"]
    assert rc.json()["action"] == "connect"
    rs = client.post("/api/connections", json={"from_id": a_id, "to_id": mid, "action": "save"})
    assert rs.status_code == 200
    assert rs.json()["id"] != conn_id

    # Idempotencia: repetir connect devuelve la misma.
    rc2 = client.post("/api/connections", json={"from_id": a_id, "to_id": mid, "action": "connect"})
    assert rc2.status_code == 200
    assert rc2.json()["id"] == conn_id

    # Listar.
    rl = client.get("/api/connections", params={"profile_id": a_id})
    assert rl.status_code == 200
    items = rl.json()
    assert len(items) == 2
    assert {i["action"] for i in items} == {"connect", "save"}
    assert all(i["profile"]["nombre"] == "Mateo Rossi" for i in items)

    # Borrar.
    rd = client.delete(f"/api/connections/{conn_id}")
    assert rd.status_code == 200 and rd.json() == {"ok": True}
    rl2 = client.get("/api/connections", params={"profile_id": a_id})
    assert len(rl2.json()) == 1

    # Errores.
    assert client.delete("/api/connections/999999").status_code == 404
    assert client.post("/api/connections",
                       json={"from_id": a_id, "to_id": a_id, "action": "connect"}).status_code == 422
    assert client.post("/api/connections",
                       json={"from_id": a_id, "to_id": mid, "action": "like"}).status_code == 422
    assert client.post("/api/connections",
                       json={"from_id": a_id, "to_id": 999999, "action": "connect"}).status_code == 404
    assert client.get("/api/connections", params={"profile_id": 999999}).status_code == 404


# ---------- Meta ----------

def test_meta(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    m = r.json()
    assert "startup_tech" in m["objetivos"] and "saas_b2b" in m["objetivos"]
    assert {"es", "en", "pt", "fr"} <= set(m["idiomas"])
    assert "GMT-3" in m["timezones"]
    assert set(m["disponibilidades"]) == {"Disponible", "Selectivo", "Ocupado"}
    assert "python" in m["skills"]
