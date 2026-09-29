"""Desglose explicable del score de matching.

Usa los helpers puros de matching.py (sin modificarlo) para devolver,
además del score total, el aporte de cada rasgo con su peso. Es lo que
alimenta la UI de scoring explicable del frontend.

Nota: a diferencia de calcular_matches() en matching.py (que pone los
scores en 0 cuando el par no pasa los filtros duros), acá se calculan
siempre los scores reales: la UI muestra el potencial aunque haya un
dealbreaker, y el motivo de descarte viene en 'motivo_descarte'.
"""

import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(_AQUI))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from matching import (  # noqa: E402
    PESOS,
    ResultadoScore,
    _campo,
    ajuste_por_objetivo,
    cobertura_necesidad_orientacion,
    complementariedad_skills,
    pasa_filtros,
    score_compatibilidad,
    similitud_escala,
    similitud_objetivos,
    similitud_rubro,
)

# (key, label ES, función de coincidencia 0-1)
_PERSONAL_TRAITS = [
    ("riesgo", "Apetito de riesgo",
     lambda a, b: similitud_escala(a["apetito_riesgo"], b["apetito_riesgo"], 4)),
    ("estilo_decision", "Estilo de decisión",
     lambda a, b: similitud_escala(a["estilo_decision"], b["estilo_decision"], 4)),
    ("horizonte", "Horizonte temporal",
     lambda a, b: similitud_escala(a["horizonte_meses"], b["horizonte_meses"], 12)),
    ("confianza", "Confianza",
     lambda a, b: similitud_escala(_campo(a, "confianza"), _campo(b, "confianza"), 4)),
    ("energia", "Energía",
     lambda a, b: similitud_escala(_campo(a, "energia"), _campo(b, "energia"), 4)),
    ("disciplina", "Disciplina",
     lambda a, b: similitud_escala(_campo(a, "disciplina"), _campo(b, "disciplina"), 4)),
    ("creatividad", "Creatividad",
     lambda a, b: similitud_escala(_campo(a, "creatividad"), _campo(b, "creatividad"), 4)),
]

_NECESIDAD_TRAITS = [
    ("skills", "Habilidades complementarias", complementariedad_skills),
    ("rubro", "Rubro compartido", similitud_rubro),
    ("inversion", "Inversión similar",
     lambda a, b: similitud_escala(a["inversion_dinero"], b["inversion_dinero"], 4)),
    ("cobertura_orientacion", "Cubre roles que te faltan",
     cobertura_necesidad_orientacion),
]


def _traits(a, b, definiciones, pesos):
    salida = []
    for key, label, fn in definiciones:
        salida.append({
            "key": key,
            "label": label,
            "coincidencia": round(float(fn(a, b)), 3),
            "peso": pesos[key],
        })
    return salida


def desglose_match(a, b):
    """Desglose completo del match entre dos perfiles (dicts del motor).

    Devuelve el dict con pasa_filtros, motivo_descarte, scores por bloque y
    total, traits explicables con pesos, y el ajuste por similitud de objetivo.
    """
    ok, motivo = pasa_filtros(a, b)
    resultado = score_compatibilidad(a, b)
    pct_obj = similitud_objetivos(a, b)
    ajuste, categoria = ajuste_por_objetivo(pct_obj)

    return {
        "pasa_filtros": ok,
        "motivo_descarte": motivo,
        "total": resultado.total,
        "compatibilidad_personal": resultado.compatibilidad_personal,
        "necesidad": resultado.necesidad,
        "personal_traits": _traits(a, b, _PERSONAL_TRAITS, PESOS["compatibilidad_personal"]),
        "necesidad_traits": _traits(a, b, _NECESIDAD_TRAITS, PESOS["necesidad"]),
        "similitud_objetivos_pct": pct_obj,
        "similitud_objetivos_categoria": categoria,
        "ajuste_objetivo": round(float(ajuste), 3),
    }
