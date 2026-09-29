"""
Prototipo de carga de perfil por consola (menús de opciones) + búsqueda
de compatibilidad contra perfiles.csv + detalle de por qué matchean.

Fase actual: opciones fijas (validación de flujo).
Fase futura: texto libre + IA para clasificar la respuesta en categorías.
"""

import pandas as pd
from matching import (
    ResultadoScore,
    pasa_filtros,
    score_compatibilidad,
    orientacion_solapamiento,
    similitud_objetivos,
    ajuste_por_objetivo,
    complementariedad_skills,
    cobertura_necesidad_orientacion,
    similitud_escala,
    similitud_rubro,
    parse_lista,
    PESOS,
)

# ---------- Opciones de menú (elegidas al azar para esta prueba) ----------
OPCIONES = {
    "orientacion": ["it", "producto", "ventas", "marketing", "inversion", "operaciones"],
    "objetivo": [
        "startup_tech", "agencia_digital", "saas_b2b", "e-commerce_brand", "infoproductos",
        "consultora_b2b", "saas_b2c", "marketplace_plataforma", "bootstrapped_microproduct", "propiedad_intelectual",
    ],
    "rubro": ["fintech", "edtech", "healthtech", "e-commerce", "foodtech"],
    "idioma": ["es", "en", "pt", "fr", "de"],
    "timezone": ["GMT-3", "GMT-5", "GMT+1", "GMT+2", "GMT+0"],
    "skills_ofrece": ["backend", "frontend", "data", "marketing", "ventas"],
    "skills_busca": ["diseno", "legal", "ventas", "producto", "finanzas"],
}


def leer_entero(mensaje, minimo, maximo):
    """Pide un entero por consola; repregunta hasta recibir uno válido y en rango."""
    while True:
        entrada = input(mensaje).strip()
        try:
            valor = int(entrada)
        except ValueError:
            print("  Ingresá una opción válida.")
            continue
        if not (minimo <= valor <= maximo):
            print(f"  Ingresá una opción dentro del rango ({minimo}-{maximo}).")
            continue
        return valor


def leer_multiples(mensaje, minimo, maximo):
    """Pide varios enteros separados por coma; valida tipo y rango de cada uno."""
    while True:
        entrada = input(mensaje).strip()
        partes = [p.strip() for p in entrada.split(",") if p.strip()]
        if not partes:
            print("  Ingresá una opción válida.")
            continue
        try:
            valores = [int(p) for p in partes]
        except ValueError:
            print("  Ingresá una opción válida.")
            continue
        fuera_de_rango = [v for v in valores if not (minimo <= v <= maximo)]
        if fuera_de_rango:
            print(f"  Ingresá una opción dentro del rango ({minimo}-{maximo}).")
            continue
        return valores


def elegir_multiple(campo):
    opciones = OPCIONES[campo]
    print(f"\n{campo} (elegí una o más, separadas por coma):")
    for i, op in enumerate(opciones, 1):
        print(f"  {i}: {op}")
    indices = leer_multiples("Tu elección (ej: 1,3): ", 1, len(opciones))
    return [opciones[i - 1] for i in indices]


def elegir_unica(campo):
    opciones = OPCIONES[campo]
    print(f"\n{campo} (elegí una opción):")
    for i, op in enumerate(opciones, 1):
        print(f"  {i}: {op}")
    indice = leer_entero("Tu elección: ", 1, len(opciones))
    return opciones[indice - 1]


def pedir_escala(campo, descripcion):
    print(f"\n{campo} — {descripcion}")
    return leer_entero("Elegí un número del 1 al 5: ", 1, 5)


def pedir_numero(campo, descripcion, minimo=1, maximo=999):
    print(f"\n{campo} — {descripcion}")
    return leer_entero("Ingresá un número: ", minimo, maximo)


def pedir_datos_usuario():
    print("=== Cargá tu perfil ===")
    perfil = {"id": input("\nTu nombre: ")}
    perfil["orientacion"] = elegir_multiple("orientacion")
    perfil["objetivo"] = elegir_unica("objetivo")
    perfil["rubro"] = elegir_multiple("rubro")
    perfil["horas_semana"] = pedir_numero("horas_semana", "horas reales por semana que podés dedicar")
    perfil["horizonte_meses"] = pedir_numero("horizonte_meses", "meses que sostendrías el proyecto sin resultados")
    perfil["idioma"] = elegir_unica("idioma")
    perfil["timezone"] = elegir_unica("timezone")
    perfil["apetito_riesgo"] = pedir_escala("apetito_riesgo", "1=muy conservador, 5=muy arriesgado")
    perfil["estilo_decision"] = pedir_escala("estilo_decision", "1=planificado, 5=prueba y error")
    perfil["confianza"] = pedir_escala("confianza", "1=recelosa, 5=confía rápido en gente nueva")
    perfil["energia"] = pedir_escala("energia", "1=calma/pausada, 5=alta intensidad")
    perfil["disciplina"] = pedir_escala("disciplina", "1=flexible/improvisa, 5=rutina estricta")
    perfil["creatividad"] = pedir_escala("creatividad", "1=metódica, 5=muy experimental")
    perfil["skills_ofrece"] = elegir_multiple("skills_ofrece")
    perfil["skills_busca"] = elegir_multiple("skills_busca")
    perfil["inversion_dinero"] = pedir_escala("inversion_dinero", "1=poco dinero a invertir, 5=mucho")
    return perfil


def buscar_compatibles(perfil_usuario, path_csv="perfiles.csv", top_n=10, umbral=0.4):
    df = pd.read_csv(path_csv)
    candidatos = df.to_dict("records")
    filas = []

    for c in candidatos:
        ok, motivo = pasa_filtros(perfil_usuario, c)
        pct_obj = similitud_objetivos(perfil_usuario, c)
        _ajuste, cat_obj = ajuste_por_objetivo(pct_obj)
        resultado = score_compatibilidad(perfil_usuario, c) if ok else ResultadoScore(0.0, 0.0, 0.0)
        filas.append({
            "candidato": c["id"],
            "pasa_filtros": ok,
            "motivo_descarte": motivo or "",
            "compatibilidad_personal": resultado.compatibilidad_personal,
            "necesidad": resultado.necesidad,
            "score": resultado.total,
            "orientacion_solapamiento": orientacion_solapamiento(perfil_usuario, c),
            "similitud_objetivos_pct": pct_obj,
            "similitud_objetivos_categoria": cat_obj,
        })

    resultados = pd.DataFrame(filas).sort_values("score", ascending=False)
    top = resultados[resultados["score"] >= umbral].head(top_n)
    if top.empty:
        print(f"\n(nadie superó {umbral}, mostrando el top {top_n} igual)")
        top = resultados.head(top_n)
    return top.reset_index(drop=True)


def formatear_tabla(top_matches):
    """Tabla minimalista: #, nombre, score (0-100), similitud de objetivo."""
    tabla = top_matches.copy()
    tabla.insert(0, "#", range(1, len(tabla) + 1))
    tabla["Similitud objetivo"] = tabla.apply(
        lambda r: f"{r['similitud_objetivos_pct']}% ({r['similitud_objetivos_categoria']})", axis=1
    )
    tabla["Score"] = (tabla["score"] * 100).round().astype(int)
    tabla = tabla.rename(columns={"candidato": "Nombre"})
    return tabla[["#", "Nombre", "Score", "Similitud objetivo"]]


def cargar_perfil_por_nombre(nombre, path_csv="perfiles.csv"):
    df = pd.read_csv(path_csv)
    fila = df[df["id"] == nombre]
    return fila.to_dict("records")[0] if not fila.empty else None


def detalle_match(perfil_usuario, candidato):
    print(f"\n{'=' * 50}")
    print(f"DETALLE: vos vs. {candidato['id']}")
    print(f"{'=' * 50}")

    campos_lista = {"orientacion", "rubro", "skills_ofrece", "skills_busca"}
    campos = ["orientacion", "objetivo", "rubro", "horas_semana", "horizonte_meses",
              "idioma", "timezone", "apetito_riesgo", "estilo_decision",
              "skills_ofrece", "skills_busca", "inversion_dinero"]

    print(f"\n{'Campo':18}{'Vos':28}{'Candidato'}")
    print("-" * 65)
    for campo in campos:
        val_u = parse_lista(perfil_usuario[campo]) if campo in campos_lista else perfil_usuario[campo]
        val_c = parse_lista(candidato[campo]) if campo in campos_lista else candidato[campo]
        print(f"{campo:18}{str(val_u):28}{str(val_c)}")

    sk = complementariedad_skills(perfil_usuario, candidato)
    ru = similitud_rubro(perfil_usuario, candidato)
    inv = similitud_escala(perfil_usuario["inversion_dinero"], candidato["inversion_dinero"], 4)
    cob = cobertura_necesidad_orientacion(perfil_usuario, candidato)

    ri = similitud_escala(perfil_usuario["apetito_riesgo"], candidato["apetito_riesgo"], 4)
    ed = similitud_escala(perfil_usuario["estilo_decision"], candidato["estilo_decision"], 4)
    ho = similitud_escala(perfil_usuario["horizonte_meses"], candidato["horizonte_meses"], 12)

    pct_obj = similitud_objetivos(perfil_usuario, candidato)
    _ajuste, cat = ajuste_por_objetivo(pct_obj)
    orient_informativo = orientacion_solapamiento(perfil_usuario, candidato)

    resultado = score_compatibilidad(perfil_usuario, candidato)

    print("\nNECESIDAD — ¿cubre algo que te falta?\n")
    print(f"  {'Rasgo':30}{'Coincidencia':>14}{'Importancia':>14}")
    for nombre, valor, peso in [
        ("Habilidades complementarias", sk, PESOS["necesidad"]["skills"]),
        ("Rubro compartido", ru, PESOS["necesidad"]["rubro"]),
        ("Inversión de dinero similar", inv, PESOS["necesidad"]["inversion"]),
        ("Cubre rol que te falta", cob, PESOS["necesidad"]["cobertura_orientacion"]),
    ]:
        print(f"  {nombre:30}{round(valor * 100):>13}%{round(peso * 100):>13}%")
    print(f"\n  Subtotal NECESIDAD: {round(resultado.necesidad * 100)} / 100")

    print("\nCOMPATIBILIDAD PERSONAL — ¿hay afinidad como personas?\n")
    print(f"  {'Rasgo':30}{'Coincidencia':>14}{'Importancia':>14}")
    for nombre, valor, peso in [
        ("Apetito de riesgo", ri, PESOS["compatibilidad_personal"]["riesgo"]),
        ("Estilo de decisión", ed, PESOS["compatibilidad_personal"]["estilo_decision"]),
        ("Horizonte temporal", ho, PESOS["compatibilidad_personal"]["horizonte"]),
        ("Confianza", similitud_escala(perfil_usuario.get("confianza", 3), candidato.get("confianza", 3), 4), PESOS["compatibilidad_personal"]["confianza"]),
        ("Energía", similitud_escala(perfil_usuario.get("energia", 3), candidato.get("energia", 3), 4), PESOS["compatibilidad_personal"]["energia"]),
        ("Disciplina", similitud_escala(perfil_usuario.get("disciplina", 3), candidato.get("disciplina", 3), 4), PESOS["compatibilidad_personal"]["disciplina"]),
        ("Creatividad", similitud_escala(perfil_usuario.get("creatividad", 3), candidato.get("creatividad", 3), 4), PESOS["compatibilidad_personal"]["creatividad"]),
    ]:
        print(f"  {nombre:30}{round(valor * 100):>13}%{round(peso * 100):>13}%")
    nota = {"positiva": "(suma puntos extra)", "negativa": "(resta puntos)", "neutral": "(no suma ni resta)"}[cat]
    print(f"  {'Similitud de objetivos/visión':30}{pct_obj:>13}%  -> {cat} {nota}")
    print(f"\n  Subtotal COMPATIBILIDAD PERSONAL: {round(resultado.compatibilidad_personal * 100)} / 100")

    print(f"\n  (informativo) Orientación en común: {round(orient_informativo * 100)}% — no afecta el score")
    print(f"\n  SCORE TOTAL: {round(resultado.total * 100)} / 100")


def menu_detalle(perfil_usuario, top_matches):
    nombres = top_matches["Nombre"].tolist()
    while True:
        print(f"\n¿Querés ver el detalle de algún perfil? Elegí del 1 al {len(nombres)} (0 para salir):")
        for i, nombre in enumerate(nombres, 1):
            print(f"  {i}: {nombre}")
        eleccion = leer_entero("> ", 0, len(nombres))
        if eleccion == 0:
            break
        candidato = cargar_perfil_por_nombre(nombres[eleccion - 1])
        detalle_match(perfil_usuario, candidato)


if __name__ == "__main__":
    perfil_usuario = pedir_datos_usuario()
    top_matches = buscar_compatibles(perfil_usuario)
    tabla = formatear_tabla(top_matches)
    print("\n=== Tus mejores matches ===")
    print(tabla.to_string(index=False))
    menu_detalle(perfil_usuario, tabla)