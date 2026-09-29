"""
Motor de compatibilidad para matching de socios.
Lee perfiles.csv, calcula compatibilidad par a par, escribe resultados.csv.

El score se divide en dos bloques conceptualmente distintos:
  - compatibilidad_personal: afinidad humana (riesgo, decisión, horizonte,
    rasgos sociales, alineación de visión/objetivo).
  - necesidad: cobertura funcional (skills complementarios, rubro, inversión,
    y qué tanto el otro cubre el hueco de roles que pide tu objetivo).
"""

import json
import os
import re
from dataclasses import dataclass
from itertools import combinations

import pandas as pd

_DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
_RUTA_CONFIG = os.path.join(_DIRECTORIO_ACTUAL, "config.json")


def _cargar_config(ruta=_RUTA_CONFIG):
    """Lee config.json y reconstruye la matriz de objetivos como frozenset
    (JSON no soporta ese tipo, se guarda como lista de pares y se convierte acá)."""
    with open(ruta, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)

    matriz = {
        frozenset(par["par"]): par["pct"]
        for par in datos["matriz_similitud_objetivos"]
    }
    return datos, matriz


_CONFIG, MATRIZ_SIMILITUD_OBJETIVOS = _cargar_config()

# ---------- Pesos, en dos bloques ----------
PESOS = _CONFIG["pesos"]
NECESIDADES_POR_OBJETIVO = _CONFIG["necesidades_por_objetivo"]

# ---------- Ajuste por similitud de objetivo (vive dentro de compatibilidad_personal) ----------
BONUS_SIMILITUD_OBJETIVO = _CONFIG["bonus_similitud_objetivo"]
PENALIZACION_SIMILITUD_OBJETIVO = _CONFIG["penalizacion_similitud_objetivo"]
UMBRAL_POSITIVO = _CONFIG["umbral_positivo"]
UMBRAL_NEGATIVO = _CONFIG["umbral_negativo"]


@dataclass
class ResultadoScore:
    """Desglose del score: los dos bloques y el total combinado (promedio simple)."""
    compatibilidad_personal: float
    necesidad: float
    total: float


def _tz_offset(tz):
    """Convierte 'GMT-3' / 'GMT+5' a un entero de horas."""
    m = re.search(r"GMT([+-]\d+)", str(tz))
    return int(m.group(1)) if m else 0


def parse_lista(valor):
    """Acepta listas en formato JSON (["a","b"]) o separadas por ';' (a;b)."""
    if isinstance(valor, list):
        return valor
    try:
        parsed = json.loads(valor)
        if isinstance(parsed, list):
            return parsed
    except (TypeError, json.JSONDecodeError, ValueError):
        pass
    return [x.strip() for x in str(valor).split(";") if x.strip()]


def _campo(perfil, clave, default=3):
    """Acceso tolerante: perfiles viejos (sin los rasgos sociales nuevos)
    no rompen el cálculo, caen en un valor neutro."""
    valor = perfil.get(clave, default)
    return default if pd.isna(valor) else valor


# ---------- Filtros duros (dealbreakers) ----------
def pasa_filtros(a, b):
    if a["idioma"] != b["idioma"]:
        return False, "idioma"

    if abs(_tz_offset(a["timezone"]) - _tz_offset(b["timezone"])) > 4:
        return False, "timezone"

    if min(a["horas_semana"], b["horas_semana"]) < 5:
        return False, "disponibilidad"

    return True, None
    # "objetivo" no es filtro: se usa como ajuste de compatibilidad_personal.


# ---------- Similitud / complementariedad ----------
def jaccard(lista_a, lista_b):
    a, b = set(lista_a), set(lista_b)
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def complementariedad_skills(a, b):
    ofrece_a = set(parse_lista(a["skills_ofrece"]))
    busca_a = set(parse_lista(a["skills_busca"]))
    ofrece_b = set(parse_lista(b["skills_ofrece"]))
    busca_b = set(parse_lista(b["skills_busca"]))

    cubre_a = len(busca_a & ofrece_b) / len(busca_a) if busca_a else 0.0
    cubre_b = len(busca_b & ofrece_a) / len(busca_b) if busca_b else 0.0
    return (cubre_a + cubre_b) / 2


def orientacion_solapamiento(a, b):
    """Solo informativo: cuánto se solapan las orientaciones. No entra al score."""
    return round(jaccard(parse_lista(a["orientacion"]), parse_lista(b["orientacion"])), 3)


def similitud_escala(x, y, max_diff):
    return max(0.0, 1 - abs(x - y) / max_diff)


def similitud_rubro(a, b):
    return jaccard(parse_lista(a["rubro"]), parse_lista(b["rubro"]))


def similitud_objetivos(a, b):
    """% de similitud entre los objetivos de dos perfiles (100 si son idénticos)."""
    obj_a, obj_b = a["objetivo"], b["objetivo"]
    if obj_a == obj_b:
        return 100
    return MATRIZ_SIMILITUD_OBJETIVOS.get(frozenset([obj_a, obj_b]), 50)


def ajuste_por_objetivo(pct):
    """Devuelve (ajuste, categoria) según la banda en la que cae el %."""
    if pct >= UMBRAL_POSITIVO:
        return BONUS_SIMILITUD_OBJETIVO, "positiva"
    if pct < UMBRAL_NEGATIVO:
        return -PENALIZACION_SIMILITUD_OBJETIVO, "negativa"
    return 0.0, "neutral"


def cobertura_necesidad_orientacion(a, b):
    """Cuánto del hueco de orientación de cada uno cubre el otro, promediado
    en las dos direcciones (igual que complementariedad_skills)."""

    def _cobertura(origen, otro):
        necesarias = NECESIDADES_POR_OBJETIVO.get(origen["objetivo"], {})
        propias = set(parse_lista(origen["orientacion"]))
        del_otro = set(parse_lista(otro["orientacion"]))

        huecos = {o: peso for o, peso in necesarias.items() if o not in propias}
        if not huecos:
            return 0.0
        peso_total = sum(huecos.values())
        peso_cubierto = sum(peso for o, peso in huecos.items() if o in del_otro)
        return peso_cubierto / peso_total if peso_total else 0.0

    return (_cobertura(a, b) + _cobertura(b, a)) / 2


# ---------- Bloque 1: compatibilidad personal ----------
def compatibilidad_personal(a, b):
    pesos = PESOS["compatibilidad_personal"]
    bruto = 0.0
    bruto += pesos["riesgo"] * similitud_escala(a["apetito_riesgo"], b["apetito_riesgo"], 4)
    bruto += pesos["estilo_decision"] * similitud_escala(a["estilo_decision"], b["estilo_decision"], 4)
    bruto += pesos["horizonte"] * similitud_escala(a["horizonte_meses"], b["horizonte_meses"], 12)
    bruto += pesos["confianza"] * similitud_escala(_campo(a, "confianza"), _campo(b, "confianza"), 4)
    bruto += pesos["energia"] * similitud_escala(_campo(a, "energia"), _campo(b, "energia"), 4)
    bruto += pesos["disciplina"] * similitud_escala(_campo(a, "disciplina"), _campo(b, "disciplina"), 4)
    bruto += pesos["creatividad"] * similitud_escala(_campo(a, "creatividad"), _campo(b, "creatividad"), 4)

    pct_obj = similitud_objetivos(a, b)
    ajuste, _categoria = ajuste_por_objetivo(pct_obj)
    return min(1.0, max(0.0, bruto + ajuste))


# ---------- Bloque 2: necesidad / cobertura funcional ----------
def necesidad(a, b):
    pesos = PESOS["necesidad"]
    n = 0.0
    n += pesos["skills"] * complementariedad_skills(a, b)
    n += pesos["rubro"] * similitud_rubro(a, b)
    n += pesos["inversion"] * similitud_escala(a["inversion_dinero"], b["inversion_dinero"], 4)
    n += pesos["cobertura_orientacion"] * cobertura_necesidad_orientacion(a, b)
    return min(1.0, max(0.0, n))


# ---------- Score compuesto ----------
def score_compatibilidad(a, b):
    personal = round(compatibilidad_personal(a, b), 3)
    func = round(necesidad(a, b), 3)
    total = round((personal + func) / 2, 3)
    return ResultadoScore(compatibilidad_personal=personal, necesidad=func, total=total)


# ---------- Motor principal ----------
def calcular_matches(path_csv="perfiles.csv"):
    df = pd.read_csv(path_csv)
    perfiles = df.to_dict("records")
    filas = []

    for a, b in combinations(perfiles, 2):
        ok, motivo = pasa_filtros(a, b)
        pct_obj = similitud_objetivos(a, b)
        _ajuste, cat_obj = ajuste_por_objetivo(pct_obj)
        resultado = score_compatibilidad(a, b) if ok else ResultadoScore(0.0, 0.0, 0.0)
        filas.append({
            "perfil_a": a["id"],
            "perfil_b": b["id"],
            "pasa_filtros": ok,
            "motivo_descarte": motivo or "",
            "compatibilidad_personal": resultado.compatibilidad_personal,
            "necesidad": resultado.necesidad,
            "score": resultado.total,
            "orientacion_solapamiento": orientacion_solapamiento(a, b),
            "similitud_objetivos_pct": pct_obj,
            "similitud_objetivos_categoria": cat_obj,
        })

    resultados = pd.DataFrame(filas).sort_values("score", ascending=False)
    resultados.to_csv("resultados.csv", index=False)
    return resultados


if __name__ == "__main__":
    resultados = calcular_matches()
    print(resultados.head(25).to_string(index=False))