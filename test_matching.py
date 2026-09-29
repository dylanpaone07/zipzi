"""
Tests de las funciones puras de matching.py (sin I/O: no tocan CSV ni consola).
Correr con: pytest -v
"""

import pytest

from matching import (
    ResultadoScore,
    ajuste_por_objetivo,
    cobertura_necesidad_orientacion,
    compatibilidad_personal,
    complementariedad_skills,
    jaccard,
    necesidad,
    parse_lista,
    pasa_filtros,
    similitud_escala,
    similitud_objetivos,
    similitud_rubro,
    score_compatibilidad,
    _tz_offset,
)


# ---------- Fixtures: perfiles mínimos reutilizables ----------
@pytest.fixture
def perfil_base():
    return {
        "id": "a",
        "orientacion": ["it"],
        "objetivo": "startup_tech",
        "rubro": ["fintech"],
        "horas_semana": 20,
        "horizonte_meses": 12,
        "idioma": "es",
        "timezone": "GMT-3",
        "apetito_riesgo": 3,
        "estilo_decision": 3,
        "confianza": 3,
        "energia": 3,
        "disciplina": 3,
        "creatividad": 3,
        "skills_ofrece": ["backend", "data"],
        "skills_busca": ["marketing", "ventas"],
        "inversion_dinero": 3,
    }


@pytest.fixture
def perfil_complementario(perfil_base):
    """Mismo idioma/timezone/disponibilidad, skills que calzan perfecto con perfil_base."""
    return {
        **perfil_base,
        "id": "b",
        "objetivo": "saas_b2b",
        "skills_ofrece": ["marketing", "ventas"],
        "skills_busca": ["backend", "data"],
    }


# ---------- jaccard ----------
def test_jaccard_sin_interseccion():
    assert jaccard(["a", "b"], ["c", "d"]) == 0.0


def test_jaccard_identicos():
    assert jaccard(["a", "b"], ["a", "b"]) == 1.0


def test_jaccard_interseccion_parcial():
    assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)


def test_jaccard_ambas_vacias():
    assert jaccard([], []) == 0.0


# ---------- similitud_escala ----------
def test_similitud_escala_valores_iguales():
    assert similitud_escala(3, 3, max_diff=4) == 1.0


def test_similitud_escala_maxima_diferencia():
    assert similitud_escala(1, 5, max_diff=4) == 0.0


def test_similitud_escala_nunca_es_negativa():
    assert similitud_escala(1, 100, max_diff=4) == 0.0


# ---------- parse_lista ----------
def test_parse_lista_formato_json():
    assert parse_lista('["it", "producto"]') == ["it", "producto"]


def test_parse_lista_formato_punto_y_coma():
    assert parse_lista("it;producto") == ["it", "producto"]


def test_parse_lista_ya_es_lista():
    assert parse_lista(["it", "producto"]) == ["it", "producto"]


# ---------- _tz_offset ----------
def test_tz_offset_negativo():
    assert _tz_offset("GMT-3") == -3


def test_tz_offset_positivo():
    assert _tz_offset("GMT+5") == 5


def test_tz_offset_formato_invalido_devuelve_cero():
    assert _tz_offset("no es un timezone") == 0


# ---------- complementariedad_skills ----------
def test_complementariedad_skills_perfecta(perfil_base, perfil_complementario):
    assert complementariedad_skills(perfil_base, perfil_complementario) == 1.0


def test_complementariedad_skills_nula(perfil_base):
    otro = {**perfil_base, "skills_ofrece": ["legal"], "skills_busca": ["diseno"]}
    assert complementariedad_skills(perfil_base, otro) == 0.0


# ---------- similitud_rubro ----------
def test_similitud_rubro_comparten_uno(perfil_base):
    otro = {**perfil_base, "rubro": ["fintech", "edtech"]}
    assert similitud_rubro(perfil_base, otro) == pytest.approx(1 / 2)


# ---------- similitud_objetivos ----------
def test_similitud_objetivos_identicos_es_100(perfil_base):
    otro = {**perfil_base, "objetivo": "startup_tech"}
    assert similitud_objetivos(perfil_base, otro) == 100


def test_similitud_objetivos_par_no_mapeado_usa_default_neutral(perfil_base):
    otro = {**perfil_base, "objetivo": "un_objetivo_que_no_esta_en_la_matriz"}
    assert similitud_objetivos(perfil_base, otro) == 50


# ---------- ajuste_por_objetivo ----------
def test_ajuste_por_objetivo_banda_positiva():
    ajuste, categoria = ajuste_por_objetivo(75)
    assert categoria == "positiva"
    assert ajuste > 0


def test_ajuste_por_objetivo_banda_negativa():
    ajuste, categoria = ajuste_por_objetivo(20)
    assert categoria == "negativa"
    assert ajuste < 0


def test_ajuste_por_objetivo_banda_neutral():
    ajuste, categoria = ajuste_por_objetivo(50)
    assert categoria == "neutral"
    assert ajuste == 0.0


# ---------- cobertura_necesidad_orientacion ----------
def test_cobertura_necesidad_orientacion_llena_todo_el_hueco(perfil_base):
    # startup_tech necesita it/producto/ventas/marketing/inversion/operaciones.
    # perfil_base solo cubre "it"; un candidato con TODO el resto cubre el 100% del hueco.
    candidato = {**perfil_base, "orientacion": ["producto", "ventas", "marketing", "inversion", "operaciones"]}
    assert cobertura_necesidad_orientacion(perfil_base, candidato) > 0.9


def test_cobertura_necesidad_orientacion_nula_si_orientaciones_iguales(perfil_base):
    igual = {**perfil_base, "orientacion": ["it"]}
    assert cobertura_necesidad_orientacion(perfil_base, igual) == 0.0


def test_cobertura_necesidad_orientacion_objetivo_no_mapeado_es_cero(perfil_base):
    otro = {**perfil_base, "objetivo": "algo_no_mapeado", "orientacion": ["producto"]}
    perfil_sin_mapa = {**perfil_base, "objetivo": "algo_no_mapeado"}
    assert cobertura_necesidad_orientacion(perfil_sin_mapa, otro) == 0.0


# ---------- pasa_filtros ----------
def test_pasa_filtros_rechaza_idioma_distinto(perfil_base):
    otro = {**perfil_base, "idioma": "en"}
    ok, motivo = pasa_filtros(perfil_base, otro)
    assert not ok
    assert motivo == "idioma"


def test_pasa_filtros_rechaza_timezone_lejana(perfil_base):
    otro = {**perfil_base, "timezone": "GMT+5"}
    ok, motivo = pasa_filtros(perfil_base, otro)
    assert not ok
    assert motivo == "timezone"


def test_pasa_filtros_rechaza_poca_disponibilidad(perfil_base):
    otro = {**perfil_base, "horas_semana": 2}
    ok, motivo = pasa_filtros(perfil_base, otro)
    assert not ok
    assert motivo == "disponibilidad"


def test_pasa_filtros_ok(perfil_base, perfil_complementario):
    ok, motivo = pasa_filtros(perfil_base, perfil_complementario)
    assert ok
    assert motivo is None


# ---------- compatibilidad_personal / necesidad (bloques por separado) ----------
def test_compatibilidad_personal_en_rango_valido(perfil_base, perfil_complementario):
    assert 0.0 <= compatibilidad_personal(perfil_base, perfil_complementario) <= 1.0


def test_necesidad_en_rango_valido(perfil_base, perfil_complementario):
    assert 0.0 <= necesidad(perfil_base, perfil_complementario) <= 1.0


def test_necesidad_tolera_perfil_sin_rasgos_sociales(perfil_base, perfil_complementario):
    # simula un perfil real "viejo" (perfiles.csv) sin confianza/energia/etc.
    viejo = dict(perfil_base)
    for campo in ("confianza", "energia", "disciplina", "creatividad"):
        viejo.pop(campo, None)
    # no debe explotar: necesidad no usa esos campos, y compatibilidad_personal
    # debe caer a un valor neutro en vez de lanzar KeyError.
    assert 0.0 <= necesidad(viejo, perfil_complementario) <= 1.0
    assert 0.0 <= compatibilidad_personal(viejo, perfil_complementario) <= 1.0


# ---------- score_compatibilidad ----------
def test_score_compatibilidad_devuelve_resultado_score(perfil_base, perfil_complementario):
    resultado = score_compatibilidad(perfil_base, perfil_complementario)
    assert isinstance(resultado, ResultadoScore)


def test_score_compatibilidad_subtotales_y_total_en_rango(perfil_base, perfil_complementario):
    resultado = score_compatibilidad(perfil_base, perfil_complementario)
    assert 0.0 <= resultado.compatibilidad_personal <= 1.0
    assert 0.0 <= resultado.necesidad <= 1.0
    assert 0.0 <= resultado.total <= 1.0


def test_score_compatibilidad_total_es_promedio_de_los_bloques(perfil_base, perfil_complementario):
    resultado = score_compatibilidad(perfil_base, perfil_complementario)
    promedio_esperado = round((resultado.compatibilidad_personal + resultado.necesidad) / 2, 3)
    assert resultado.total == promedio_esperado