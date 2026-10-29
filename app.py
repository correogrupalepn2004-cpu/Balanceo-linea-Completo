"""
Plataforma MES - Estudio de tiempos, análisis de valor, TOC y balanceo de líneas (COMSOAL)
Escuela Politécnica Nacional (EPN) - Aplicación genérica para cualquier estudio.
"""
import datetime
import json
import math
import random
import re
from io import BytesIO

import graphviz
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ==========================================================
# 0. CONFIGURACIÓN, PALETA Y ESTILO
# ==========================================================
AZUL, ROJO, GRIS, FONDO, BORDE = "#003366", "#ff4b4b", "#94a3b8", "#f8f9fa", "#e2e8f0"
VERDE = "#2e8b57"

st.set_page_config(page_title="MES - EPN", page_icon="🏭", layout="wide")

st.markdown(
    f"""
<style>
[data-testid="stMetric"] {{
    background: {FONDO}; border: 1px solid {BORDE}; border-left: 4px solid {AZUL};
    border-radius: 6px; padding: 12px 16px; box-shadow: none;
}}
[data-testid="stMetricLabel"] p {{ color: #475569; font-size: 0.85rem; }}
h1, h2, h3 {{ color: {AZUL}; font-family: 'Segoe UI', sans-serif; }}
[data-testid="stSidebar"] {{ background: {FONDO}; border-right: 1px solid {BORDE}; }}
.stButton > button, .stDownloadButton > button {{ box-shadow: none; border-radius: 6px; }}
.nota {{ background:{FONDO}; border:1px solid {BORDE}; border-radius:6px; padding:10px 14px; color:#334155; }}
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# 1. CONSTANTES DEL MODELO
# ==========================================================
SIMBOLOS = ["Operación", "Inspección", "Transporte", "Demora", "Almacenaje"]
COLOR_SIMBOLO = {
    "Operación": AZUL, "Inspección": "#5b7fa6", "Transporte": ROJO,
    "Demora": "#e8590c", "Almacenaje": GRIS,
}
OBS_COLS = [f"Obs {i}" for i in range(1, 6)]
BOM_COLS = ["Código", "Descripción", "Cantidad", "Unidad", "Inyectado en Tarea"]
TIEMPOS_COLS = ["ID Tarea", "Descripción", "Preds"] + OBS_COLS
CURSO_COLS = ["ID Tarea", "Símbolo", "Distancia (m)"]
TOC_COLS = ["Estación", "t0 (min/lote)", "Máquinas"]
SUPL_COLS = ["Concepto", "Tipo", "Aplica", "%"]

# Tablas del sistema Westinghouse
HABILIDAD = {
    "A1 Superhábil (+0.15)": 0.15, "A2 Superhábil (+0.13)": 0.13, "B1 Excelente (+0.11)": 0.11,
    "B2 Excelente (+0.08)": 0.08, "C1 Bueno (+0.06)": 0.06, "C2 Bueno (+0.03)": 0.03,
    "D Medio (0.00)": 0.0, "E1 Aceptable (-0.05)": -0.05, "E2 Aceptable (-0.10)": -0.10,
    "F1 Deficiente (-0.16)": -0.16, "F2 Deficiente (-0.22)": -0.22,
}
ESFUERZO = {
    "A1 Excesivo (+0.13)": 0.13, "A2 Excesivo (+0.12)": 0.12, "B1 Excelente (+0.10)": 0.10,
    "B2 Excelente (+0.08)": 0.08, "C1 Bueno (+0.05)": 0.05, "C2 Bueno (+0.02)": 0.02,
    "D Medio (0.00)": 0.0, "E1 Aceptable (-0.04)": -0.04, "E2 Aceptable (-0.08)": -0.08,
    "F1 Deficiente (-0.12)": -0.12, "F2 Deficiente (-0.17)": -0.17,
}
CONDICIONES = {
    "A Ideales (+0.06)": 0.06, "B Excelentes (+0.04)": 0.04, "C Buenas (+0.02)": 0.02,
    "D Medias (0.00)": 0.0, "E Aceptables (-0.03)": -0.03, "F Deficientes (-0.07)": -0.07,
}
CONSISTENCIA = {
    "A Perfecta (+0.04)": 0.04, "B Excelente (+0.03)": 0.03, "C Buena (+0.01)": 0.01,
    "D Media (0.00)": 0.0, "E Aceptable (-0.02)": -0.02, "F Deficiente (-0.04)": -0.04,
}

CFG_DEFECTO = {
    "institucion": "Escuela Politécnica Nacional", "autor": "", "producto": "",
    "fecha": str(datetime.date.today()),
    "habilidad": "D Medio (0.00)", "esfuerzo": "D Medio (0.00)",
    "condiciones": "D Medias (0.00)", "consistencia": "D Media (0.00)",
    "ciclo": 40.0, "iteraciones": 2000, "semilla": 42,
    "demanda": 600, "disponible_min": 420.0,
    "lambda_h": 10.0, "phi_auto": True, "phi_min": 60.0,
}


def supl_defecto():
    """Suplementos OIT referenciales (editables por el usuario)."""
    filas = [
        ("Necesidades personales", "Constante", True, 5.0),
        ("Fatiga básica", "Constante", True, 4.0),
        ("Trabajo de pie", "Variable", True, 2.0),
        ("Postura incómoda", "Variable", False, 2.0),
        ("Uso de fuerza / levantamiento de peso", "Variable", False, 3.0),
        ("Mala iluminación", "Variable", False, 2.0),
        ("Ruido intermitente", "Variable", False, 2.0),
        ("Tensión visual", "Variable", False, 2.0),
        ("Monotonía / tedio", "Variable", False, 1.0),
    ]
    return pd.DataFrame(filas, columns=SUPL_COLS)


# ==========================================================
# 2. PROYECTOS: VACÍO, EJEMPLO, GUARDAR Y CARGAR
# ==========================================================
def proyecto_vacio():
    return {
        "cfg": dict(CFG_DEFECTO),
        "bom": pd.DataFrame([["", "", 1.0, "u", ""]], columns=BOM_COLS),
        "tiempos": pd.DataFrame([["T1", "", "", None, None, None, None, None]], columns=TIEMPOS_COLS),
        "supl": supl_defecto(),
        "cursograma": pd.DataFrame(columns=CURSO_COLS),
        "toc": pd.DataFrame([["E1", 0.0, 1]], columns=TOC_COLS),
    }


def proyecto_ejemplo():
    p = proyecto_vacio()
    p["cfg"].update({"producto": "Salsa de queso cheddar 250 ml", "autor": "Estudiante EPN", "ciclo": 40.0})
    p["bom"] = pd.DataFrame(
        [
            ["P-01", "Envase plástico 250 ml", 1.0, "u", "T1"],
            ["P-02", "Salsa queso cheddar", 240.0, "g", "T2"],
            ["E-01", "Tapa flip top", 1.0, "u", "T3"],
            ["E-02", "Etiqueta frontal", 1.0, "u", "T5"],
            ["E-03", "Caja corrugada", 0.1, "u", "T8"],
        ],
        columns=BOM_COLS,
    )
    filas = [
        ("T1", "Posicionar envase", "", [12, 12.5, 11.8]),
        ("T2", "Dosificar salsa", "T1", [20, 19.5, 20.5]),
        ("T3", "Colocar y sellar tapa", "T2", [14, 13.6, 14.4]),
        ("T4", "Limpiar rebose", "T2", [9, 9.4, 8.8]),
        ("T5", "Etiquetar", "T3", [16, 15.5, 16.2]),
        ("T6", "Inspección de calidad", "T4,T5", [11, 10.7, 11.3]),
        ("T7", "Transportar a empaque", "T6", [8, 8.2, 7.9]),
        ("T8", "Empacar en caja", "T7", [18, 17.6, 18.3]),
    ]
    p["tiempos"] = pd.DataFrame(
        [[i, d, pr] + o + [None] * (5 - len(o)) for i, d, pr, o in filas], columns=TIEMPOS_COLS
    )
    p["cursograma"] = pd.DataFrame(
        [
            ["T1", "Operación", 0.0], ["T2", "Operación", 0.0], ["T3", "Operación", 0.0],
            ["T4", "Operación", 0.0], ["T5", "Operación", 0.0], ["T6", "Inspección", 0.0],
            ["T7", "Transporte", 12.0], ["T8", "Operación", 0.0],
        ],
        columns=CURSO_COLS,
    )
    p["toc"] = pd.DataFrame(
        [["Dosificado", 4.0, 1], ["Sellado", 5.0, 1], ["Etiquetado", 3.5, 1], ["Empaque", 6.0, 1]],
        columns=TOC_COLS,
    )
    p["cfg"]["lambda_h"] = 10.0
    return p


def a_registros(df: pd.DataFrame):
    return json.loads(df.to_json(orient="records", force_ascii=False))


def exportar_json() -> str:
    P = st.session_state.P
    return json.dumps(
        {
            "version": 2,
            "cfg": P["cfg"],
            "bom": a_registros(P["bom"]),
            "tiempos": a_registros(P["tiempos"]),
            "supl": a_registros(P["supl"]),
            "cursograma": a_registros(P["cursograma"]),
            "toc": a_registros(P["toc"]),
        },
        ensure_ascii=False,
        indent=2,
    )


def _df(registros, columnas):
    df = pd.DataFrame(registros)
    for c in columnas:
        if c not in df.columns:
            df[c] = None
    return df[columnas]


def importar_json(data: dict):
    """Acepta tanto el formato nuevo como el JSON antiguo de la primera versión."""
    p = proyecto_vacio()
    cfg = data.get("cfg") or {}
    meta = data.get("meta") or {}  # formato antiguo
    p["cfg"].update({k: v for k, v in {**meta, **cfg}.items() if k in CFG_DEFECTO})

    bom = pd.DataFrame(data.get("bom", []))
    bom = bom.rename(columns={"Cant": "Cantidad", "Tarea Destino": "Inyectado en Tarea"})
    p["bom"] = _df(bom.to_dict("records"), BOM_COLS) if len(bom) else p["bom"]

    t = pd.DataFrame(data.get("tiempos", []))
    if len(t):
        if "Tiempo Observado (s)" in t.columns and "Obs 1" not in t.columns:
            t["Obs 1"] = t["Tiempo Observado (s)"]
        p["tiempos"] = _df(t.to_dict("records"), TIEMPOS_COLS)

    if data.get("supl"):
        p["supl"] = _df(data["supl"], SUPL_COLS)
    c = pd.DataFrame(data.get("cursograma", []))
    if len(c):
        c["Símbolo"] = c["Símbolo"].replace({"Espera": "Demora"})
        p["cursograma"] = _df(c.to_dict("records"), CURSO_COLS)
    if data.get("toc"):
        p["toc"] = _df(data["toc"], TOC_COLS)
    return p


def cb_nuevo():
    st.session_state.P = proyecto_vacio()
    st.session_state.res = None
    st.session_state.flash = ("ok", "Proyecto nuevo creado.")


def cb_ejemplo():
    st.session_state.P = proyecto_ejemplo()
    st.session_state.res = None
    st.session_state.flash = ("ok", "Ejemplo cargado. Puedes editar cualquier tabla.")


def cb_cargar():
    f = st.session_state.get("up_json")
    if f is None:
        st.session_state.flash = ("warn", "Primero selecciona un archivo .json.")
        return
    try:
        st.session_state.P = importar_json(json.load(f))
        st.session_state.res = None
        st.session_state.flash = ("ok", "Proyecto cargado correctamente.")
    except Exception as e:  # noqa: BLE001
        st.session_state.flash = ("err", f"No se pudo leer el archivo: {e}")


if "P" not in st.session_state:
    st.session_state.P = proyecto_ejemplo()
if "res" not in st.session_state:
    st.session_state.res = None

P = st.session_state.P
cfg = P["cfg"]


# ==========================================================
# 3. LÓGICA DE NEGOCIO (funciones puras, reutilizables)
# ==========================================================
def parse_preds(s) -> list:
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return []
    partes = re.split(r"[,;\s]+", str(s).strip())
    return [p for p in partes if p and p.lower() not in ("nan", "none")]


def factores():
    """RF (Westinghouse) y suma de suplementos (OIT) desde la configuración."""
    rf = 1 + HABILIDAD[cfg["habilidad"]] + ESFUERZO[cfg["esfuerzo"]] \
        + CONDICIONES[cfg["condiciones"]] + CONSISTENCIA[cfg["consistencia"]]
    s = P["supl"].copy()
    s["%"] = pd.to_numeric(s["%"], errors="coerce").fillna(0.0)
    aplica = s["Aplica"].fillna(False).astype(bool)
    suplementos = float(s.loc[aplica, "%"].sum()) / 100.0
    return rf, suplementos


def calcular_tiempos() -> pd.DataFrame:
    """Operación vectorizada: TN = TO × RF ; TS = TN × (1 + Σ suplementos)."""
    d = P["tiempos"].copy()
    d["ID Tarea"] = d["ID Tarea"].fillna("").astype(str).str.strip()
    d["Descripción"] = d["Descripción"].fillna("").astype(str)
    d["Preds"] = d["Preds"].fillna("").astype(str)
    d = d[d["ID Tarea"] != ""].reset_index(drop=True)
    for c in OBS_COLS:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    rf, sup = factores()
    d["T. Observado (s)"] = d[OBS_COLS].mean(axis=1, skipna=True).fillna(0.0)
    d["Tiempo Normal (s)"] = d["T. Observado (s)"] * rf
    d["Tiempo Estándar (s)"] = d["Tiempo Normal (s)"] * (1 + sup)
    return d


def validar(tc: pd.DataFrame):
    """Devuelve (errores, avisos). Los errores impiden ejecutar el balanceo."""
    errores, avisos = [], []
    if tc.empty:
        return ["No hay tareas definidas en el Módulo 2."], avisos
    ids = tc["ID Tarea"].tolist()
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errores.append(f"IDs de tarea repetidos: {', '.join(dup)}.")
    conjunto = set(ids)
    grafo = {}
    for _, r in tc.iterrows():
        ps = parse_preds(r["Preds"])
        grafo[r["ID Tarea"]] = ps
        if r["ID Tarea"] in ps:
            errores.append(f"La tarea {r['ID Tarea']} se tiene a sí misma como predecesora.")
        faltan = [p for p in ps if p not in conjunto]
        if faltan:
            errores.append(f"La tarea {r['ID Tarea']} usa predecesores inexistentes: {', '.join(faltan)}.")
    # detección de ciclos (Kahn)
    if not errores:
        grado = {t: len(ps) for t, ps in grafo.items()}
        cola = [t for t, g in grado.items() if g == 0]
        visitados = 0
        while cola:
            x = cola.pop()
            visitados += 1
            for t, ps in grafo.items():
                if x in ps:
                    grado[t] -= 1
                    if grado[t] == 0:
                        cola.append(t)
        if visitados != len(grafo):
            errores.append("Las precedencias forman un ciclo (por ejemplo A→B→A). Revisa la columna Preds.")
    sin_tiempo = tc.loc[tc["T. Observado (s)"] <= 0, "ID Tarea"].tolist()
    if sin_tiempo:
        avisos.append(f"Tareas sin tiempo observado: {', '.join(sin_tiempo)}.")
    return errores, avisos


def comsoal(dur: dict, preds: dict, C: float, iteraciones: int, semilla: int):
    """
    COMSOAL: en cada iteración arma una solución factible eligiendo al azar
    entre las tareas disponibles (precedencias cumplidas y que caben en la estación).
    Se conserva la mejor: menos estaciones y, en empate, menor índice de suavidad.
    """
    rng = random.Random(semilla)
    ids = list(dur)
    mejor, mejor_clave, historial = None, None, []
    for _ in range(int(iteraciones)):
        hechas, pendientes = set(), list(ids)
        estaciones, actual, t_act = [], [], 0.0
        while pendientes:
            disp = [x for x in pendientes
                    if all(p in hechas for p in preds[x]) and dur[x] <= C - t_act + 1e-9]
            if disp:
                x = rng.choice(disp)
                actual.append(x)
                hechas.add(x)
                pendientes.remove(x)
                t_act += dur[x]
            else:
                if not actual:  # nada cabe ni en una estación vacía
                    raise ValueError("Ninguna tarea disponible cabe en el tiempo de ciclo.")
                estaciones.append({"tareas": actual, "tiempo": t_act})
                actual, t_act = [], 0.0
        if actual:
            estaciones.append({"tareas": actual, "tiempo": t_act})
        tiempos = [e["tiempo"] for e in estaciones]
        smax = max(tiempos)
        IS = math.sqrt(sum((smax - s) ** 2 for s in tiempos))
        historial.append((len(estaciones), IS))
        clave = (len(estaciones), IS)
        if mejor_clave is None or clave < mejor_clave:
            mejor, mejor_clave = estaciones, clave
    return {"estaciones": mejor, "IS": mejor_clave[1], "historial": historial}


def sincronizar_cursograma(tc: pd.DataFrame) -> pd.DataFrame:
    """El cursograma siempre usa las tareas del Módulo 2 y conserva lo ya clasificado."""
    previo = P["cursograma"].drop_duplicates("ID Tarea") if len(P["cursograma"]) else \
        pd.DataFrame(columns=CURSO_COLS)
    base = tc[["ID Tarea"]].merge(previo, on="ID Tarea", how="left")
    base["Símbolo"] = base["Símbolo"].where(base["Símbolo"].isin(SIMBOLOS), "Operación")
    base["Distancia (m)"] = pd.to_numeric(base["Distancia (m)"], errors="coerce").fillna(0.0)
    P["cursograma"] = base
    return base


def construir_excel() -> bytes:
    tc = calcular_tiempos()
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        pd.DataFrame(
            {"Campo": ["Institución", "Analista", "Producto", "Fecha"],
             "Valor": [cfg["institucion"], cfg["autor"], cfg["producto"], cfg["fecha"]]}
        ).to_excel(xw, "Proyecto", index=False)
        P["bom"].to_excel(xw, "BOM", index=False)
        tc.to_excel(xw, "Tiempos", index=False)
        P["supl"].to_excel(xw, "Suplementos", index=False)
        P["cursograma"].to_excel(xw, "Cursograma", index=False)
        P["toc"].to_excel(xw, "TOC", index=False)
        res = st.session_state.get("res")
        if res:
            filas = []
            for k, e in enumerate(res["estaciones"], 1):
                for t in e["tareas"]:
                    filas.append({"Estación": k, "Tarea": t, "Tiempo estándar (s)": res["dur"][t]})
            pd.DataFrame(filas).to_excel(xw, "Balanceo", index=False)
    return buf.getvalue()


# ==========================================================
# 4. BARRA LATERAL
# ==========================================================
with st.sidebar:
    st.markdown(f"<h2 style='margin:0;color:{AZUL}'>🏭 MES · EPN</h2>", unsafe_allow_html=True)
    st.caption("Tiempos · Valor · TOC · Balanceo de líneas")

    modulo = st.radio(
        "Navegación",
        ["Inicio", "1. BOM y ensamble", "2. Estudio de tiempos", "3. Cursograma y valor",
         "4. Teoría de restricciones", "5. Balanceo COMSOAL"],
    )

    st.divider()
    st.markdown("**Proyecto**")
    b1, b2 = st.columns(2)
    b1.button("Nuevo", on_click=cb_nuevo, help="Empieza un proyecto en blanco")
    b2.button("Ejemplo", on_click=cb_ejemplo, help="Carga un caso de demostración")
    st.file_uploader("Abrir proyecto (.json)", type="json", key="up_json")
    st.button("Cargar archivo", on_click=cb_cargar)
    st.download_button("Guardar progreso (.json)", exportar_json(),
                       file_name="proyecto_mes.json", mime="application/json")
    try:
        st.download_button(
            "Exportar informe (.xlsx)", construir_excel(), file_name="informe_mes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:  # noqa: BLE001
        st.caption("El informe Excel estará disponible cuando los datos sean válidos.")

    st.divider()
    st.markdown("**Datos del estudio**")
    cfg["institucion"] = st.text_input("Institución", cfg["institucion"])
    cfg["autor"] = st.text_input("Analista", cfg["autor"])
    cfg["producto"] = st.text_input("Producto", cfg["producto"])

if st.session_state.get("flash"):
    tipo, msg = st.session_state.pop("flash")
    {"ok": st.success, "warn": st.warning, "err": st.error}[tipo](msg)

tc = calcular_tiempos()


# ==========================================================
# INICIO
# ==========================================================
if modulo == "Inicio":
    st.title("Plataforma MES para estudios de línea")
    st.markdown(
        "Esta herramienta te guía desde el levantamiento de tiempos hasta la línea de ensamble "
        "balanceada. Sirve para cualquier producto o proceso: reemplaza el ejemplo con tus datos."
    )
    rf, sup = factores()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tareas definidas", len(tc))
    c2.metric("Tiempo estándar total", f"{tc['Tiempo Estándar (s)'].sum():.1f} s")
    c3.metric("Factor de ritmo (RF)", f"{rf:.2f}")
    c4.metric("Suplementos", f"{sup * 100:.0f} %")

    st.markdown("### Cómo usarla")
    st.markdown(
        """
1. **BOM y ensamble:** lista los materiales y a qué tarea entra cada uno.
2. **Estudio de tiempos:** registra hasta 5 observaciones por tarea; la app calcula tiempo normal y estándar.
3. **Cursograma y valor:** clasifica cada tarea con la simbología ASME y mira cuánto tiempo agrega valor.
4. **Teoría de restricciones:** con la ley de Little, identifica el cuello de botella.
5. **Balanceo COMSOAL:** define el tiempo de ciclo (o calcúlalo desde la demanda) y obtén las estaciones.

Guarda tu avance con **Guardar progreso** y ábrelo cuando quieras. **Exportar informe** genera un Excel con todo el estudio.
"""
    )
    st.markdown(
        "<div class='nota'>Las tareas se escriben una sola vez, en el módulo 2. "
        "Los demás módulos las leen desde ahí.</div>",
        unsafe_allow_html=True,
    )

# ==========================================================
# MÓDULO 1: BOM
# ==========================================================
elif modulo == "1. BOM y ensamble":
    st.title("Lista de materiales (BOM) y ensamble")
    st.markdown("Indica qué materiales usa el producto y en qué tarea se incorpora cada uno.")

    P["bom"] = st.data_editor(
        P["bom"], num_rows="dynamic",
        column_config={
            "Cantidad": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "Unidad": st.column_config.SelectboxColumn(
                options=["u", "g", "kg", "ml", "l", "m", "cm", "m²", "lb", "oz"]),
            "Inyectado en Tarea": st.column_config.TextColumn(help="ID de la tarea (debe existir en el módulo 2)"),
        },
    )

    bom = P["bom"].copy()
    bom["Inyectado en Tarea"] = bom["Inyectado en Tarea"].fillna("").astype(str).str.strip()
    bom["Código"] = bom["Código"].fillna("").astype(str).str.strip()
    bom = bom[bom["Código"] != ""]
    ids = set(tc["ID Tarea"])
    huerfanos = bom.loc[(bom["Inyectado en Tarea"] != "") & (~bom["Inyectado en Tarea"].isin(ids)), "Código"]
    if len(huerfanos):
        st.warning(f"Materiales asignados a tareas que no existen en el módulo 2: {', '.join(huerfanos)}.")
    sin_tarea = bom.loc[bom["Inyectado en Tarea"] == "", "Código"]
    if len(sin_tarea):
        st.info(f"Materiales sin tarea asignada (no aparecen en el diagrama): {', '.join(sin_tarea)}.")

    st.subheader("Árbol de ensamble")
    dot = graphviz.Digraph()
    dot.attr(rankdir="LR", nodesep="0.35")
    dot.attr("node", fontname="Helvetica", fontsize="11")
    dot.node("PROD", cfg["producto"] or "Producto terminado", shape="folder",
             style="filled", fillcolor=AZUL, fontcolor="white")
    todas_preds = set()
    for _, r in tc.iterrows():
        todas_preds.update(parse_preds(r["Preds"]))
    for _, r in tc.iterrows():
        dot.node(r["ID Tarea"], f"{r['ID Tarea']}\n{r['Descripción']}", shape="box",
                 style="rounded,filled", fillcolor=BORDE)
        for p in parse_preds(r["Preds"]):
            if p in ids:
                dot.edge(p, r["ID Tarea"])
        if r["ID Tarea"] not in todas_preds:
            dot.edge(r["ID Tarea"], "PROD")
    for _, r in bom.iterrows():
        if r["Inyectado en Tarea"] == "":
            continue
        nodo = "mat_" + r["Código"]
        dot.node(nodo, f"{r['Código']}\n{r['Descripción']}", shape="note", style="filled", fillcolor="white")
        if r["Inyectado en Tarea"] not in ids:
            dot.node(r["Inyectado en Tarea"], r["Inyectado en Tarea"] + "\n(no definida)", shape="box",
                     style="dashed,filled", fillcolor="#ffe3e3")
        dot.edge(nodo, r["Inyectado en Tarea"], label=f" {r['Cantidad']:g} {r['Unidad']}")
    st.graphviz_chart(dot)

    if len(bom):
        st.subheader("Materiales por tarea")
        resumen = (bom[bom["Inyectado en Tarea"] != ""]
                   .groupby("Inyectado en Tarea")
                   .agg(Materiales=("Código", "count"), Detalle=("Descripción", lambda s: ", ".join(s.astype(str))))
                   .reset_index())
        st.dataframe(resumen, hide_index=True)

# ==========================================================
# MÓDULO 2: TIEMPOS
# ==========================================================
elif modulo == "2. Estudio de tiempos":
    st.title("Estudio de tiempos estandarizado")

    st.markdown("### 1. Parámetros del operador y del entorno")
    st.caption("Sistema Westinghouse: valora el ritmo del operador observado.")
    c1, c2, c3, c4 = st.columns(4)
    for col, clave, nombre, tabla in [
        (c1, "habilidad", "Habilidad", HABILIDAD), (c2, "esfuerzo", "Esfuerzo", ESFUERZO),
        (c3, "condiciones", "Condiciones", CONDICIONES), (c4, "consistencia", "Consistencia", CONSISTENCIA),
    ]:
        opciones = list(tabla)
        if cfg[clave] not in opciones:
            cfg[clave] = opciones[opciones.index(next(o for o in opciones if tabla[o] == 0.0))]
        cfg[clave] = col.selectbox(nombre, opciones, index=opciones.index(cfg[clave]))

    st.caption("Suplementos OIT: marca los que aplican y ajusta los porcentajes. Puedes agregar filas.")
    P["supl"] = st.data_editor(
        P["supl"], num_rows="dynamic",
        column_config={
            "Tipo": st.column_config.SelectboxColumn(options=["Constante", "Variable"]),
            "Aplica": st.column_config.CheckboxColumn(),
            "%": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f"),
        },
    )
    rf, sup = factores()
    m1, m2, m3 = st.columns(3)
    m1.metric("Factor de ritmo (RF)", f"{rf:.2f}")
    m2.metric("Suplementos totales", f"{sup * 100:.1f} %")
    m3.metric("Multiplicador global", f"{rf * (1 + sup):.3f}")

    st.markdown("### 2. Tabla de cronometraje (segundos)")
    st.caption("Ingresa una o varias observaciones por tarea; se usa su promedio. "
               "En Preds escribe los IDs de las tareas anteriores separados por coma (ej.: T1,T2).")
    P["tiempos"] = st.data_editor(
        P["tiempos"], num_rows="dynamic",
        column_config={c: st.column_config.NumberColumn(min_value=0.0, format="%.2f") for c in OBS_COLS},
    )
    tc = calcular_tiempos()

    errores, avisos = validar(tc)
    for e in errores:
        st.error(e)
    for a in avisos:
        st.warning(a)

    st.markdown("### 3. Resultados")
    res = tc[["ID Tarea", "Descripción", "T. Observado (s)", "Tiempo Normal (s)", "Tiempo Estándar (s)"]]
    st.dataframe(res.style.format({c: "{:.2f}" for c in res.columns[2:]}), hide_index=True)

    if len(tc):
        i_max = tc["Tiempo Estándar (s)"].idxmax()
        colores = [ROJO if i == i_max else GRIS for i in tc.index]
        fig = go.Figure(go.Bar(x=tc["ID Tarea"], y=tc["Tiempo Estándar (s)"], marker_color=colores,
                               text=tc["Tiempo Estándar (s)"].round(1), textposition="outside"))
        fig.update_layout(title="Tiempo estándar por tarea (la más larga en rojo)",
                          yaxis_title="segundos", plot_bgcolor="white", margin=dict(t=50))
        fig.update_yaxes(gridcolor=BORDE)
        st.plotly_chart(fig)
        st.markdown(
            f"<div class='nota'>La tarea más larga es <b>{tc.loc[i_max, 'ID Tarea']}</b> "
            f"({tc.loc[i_max, 'Tiempo Estándar (s)']:.1f} s). El tiempo de ciclo del balanceo no puede ser menor a ese valor.</div>",
            unsafe_allow_html=True,
        )

# ==========================================================
# MÓDULO 3: CURSOGRAMA
# ==========================================================
elif modulo == "3. Cursograma y valor":
    st.title("Cursograma analítico y análisis de valor")
    if tc.empty:
        st.info("Define primero las tareas en el módulo 2.")
        st.stop()

    base = sincronizar_cursograma(tc)
    vista = tc[["ID Tarea", "Descripción", "Tiempo Estándar (s)"]].merge(base, on="ID Tarea", how="left")
    vista = vista[["ID Tarea", "Descripción", "Símbolo", "Distancia (m)", "Tiempo Estándar (s)"]]

    st.markdown("### 1. Clasificación ASME")
    st.caption("Las tareas vienen del módulo 2. Elige el símbolo de cada una y, si es transporte, la distancia.")
    ed = st.data_editor(
        vista, disabled=["ID Tarea", "Descripción", "Tiempo Estándar (s)"],
        column_config={
            "Símbolo": st.column_config.SelectboxColumn(options=SIMBOLOS, required=True),
            "Distancia (m)": st.column_config.NumberColumn(min_value=0.0, format="%.1f"),
            "Tiempo Estándar (s)": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    P["cursograma"] = ed[CURSO_COLS].copy()
    df = ed.copy()
    df["Tipo"] = np.where(df["Símbolo"] == "Operación", "Agrega valor (VA)", "No agrega valor (NVA)")

    t_total = df["Tiempo Estándar (s)"].sum()
    t_va = df.loc[df["Tipo"].str.startswith("Agrega"), "Tiempo Estándar (s)"].sum()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tiempo VA", f"{t_va:.1f} s")
    k2.metric("Tiempo NVA", f"{t_total - t_va:.1f} s")
    k3.metric("% valor agregado", f"{(t_va / t_total * 100) if t_total else 0:.1f} %")
    k4.metric("Distancia recorrida", f"{df['Distancia (m)'].sum():.1f} m")

    st.markdown("### 2. Análisis visual")
    g1, g2 = st.columns(2)
    with g1:
        pos = {s: i for i, s in enumerate(SIMBOLOS)}
        d2 = df.reset_index(drop=True)
        x = d2["Símbolo"].map(pos)
        y = list(range(len(d2), 0, -1))
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=GRIS, width=2),
                                 hoverinfo="skip", showlegend=False))
        for s in SIMBOLOS:
            m = d2["Símbolo"] == s
            if m.any():
                fig.add_trace(go.Scatter(
                    x=x[m], y=[yy for yy, k in zip(y, m) if k], mode="markers+text", name=s,
                    text=d2.loc[m, "ID Tarea"], textposition="middle right",
                    marker=dict(size=15, color=COLOR_SIMBOLO[s], line=dict(color="white", width=1)),
                    customdata=np.stack([d2.loc[m, "Descripción"], d2.loc[m, "Tiempo Estándar (s)"],
                                         d2.loc[m, "Distancia (m)"]], axis=-1),
                    hovertemplate="<b>%{text}</b> %{customdata[0]}<br>%{customdata[1]:.1f} s · %{customdata[2]:.1f} m<extra></extra>",
                ))
        fig.update_layout(
            title="Diagrama de flujo (espagueti): transportes y demoras en rojo",
            xaxis=dict(tickvals=list(pos.values()), ticktext=list(pos.keys()), range=[-0.5, len(SIMBOLOS) - 0.3]),
            yaxis=dict(showticklabels=False, showgrid=False), plot_bgcolor="white",
            legend=dict(orientation="h", y=-0.15), margin=dict(t=50),
        )
        fig.update_xaxes(gridcolor=BORDE)
        st.plotly_chart(fig)

    with g2:
        resumen = df.groupby("Tipo")["Tiempo Estándar (s)"].sum().reset_index()
        fig2 = px.pie(resumen, values="Tiempo Estándar (s)", names="Tipo", hole=0.5,
                      title="Tiempo con y sin valor agregado", color="Tipo",
                      color_discrete_map={"Agrega valor (VA)": VERDE, "No agrega valor (NVA)": ROJO})
        fig2.update_layout(margin=dict(t=50))
        st.plotly_chart(fig2)

    st.markdown("### 3. Resumen por símbolo")
    por_simbolo = (df.groupby("Símbolo").agg(Actividades=("ID Tarea", "count"),
                                              Tiempo_s=("Tiempo Estándar (s)", "sum"),
                                              Distancia_m=("Distancia (m)", "sum"))
                   .reindex(SIMBOLOS).fillna(0).reset_index())
    por_simbolo.columns = ["Símbolo", "Actividades", "Tiempo (s)", "Distancia (m)"]
    st.dataframe(por_simbolo.style.format({"Tiempo (s)": "{:.1f}", "Distancia (m)": "{:.1f}"}), hide_index=True)

    nva = df[df["Tipo"].str.startswith("No")].sort_values("Tiempo Estándar (s)", ascending=False)
    if len(nva):
        top = nva.iloc[0]
        st.markdown(
            f"<div class='nota'>Mayor desperdicio: <b>{top['ID Tarea']} · {top['Descripción']}</b> "
            f"({top['Símbolo'].lower()}, {top['Tiempo Estándar (s)']:.1f} s). "
            "Es la primera candidata a eliminar o reducir.</div>", unsafe_allow_html=True)

# ==========================================================
# MÓDULO 4: TOC
# ==========================================================
elif modulo == "4. Teoría de restricciones":
    st.title("Teoría de restricciones (ley de Little)")
    st.markdown("Con la tasa de llegada y el tiempo de proceso de cada estación, la app identifica el cuello de botella.")

    st.markdown("### 1. Estaciones o máquinas")
    cb1, _ = st.columns([1, 3])
    if cb1.button("Importar desde balanceo", help="Usa las estaciones de la última corrida COMSOAL"):
        r = st.session_state.get("res")
        if r:
            P["toc"] = pd.DataFrame(
                [[f"Estación {i}", round(e["tiempo"] / 60, 3), 1] for i, e in enumerate(r["estaciones"], 1)],
                columns=TOC_COLS)
            st.rerun()
        else:
            st.warning("Primero ejecuta el balanceo en el módulo 5.")

    P["toc"] = st.data_editor(
        P["toc"], num_rows="dynamic",
        column_config={
            "t0 (min/lote)": st.column_config.NumberColumn(min_value=0.0, format="%.2f",
                                                           help="Tiempo de proceso de un lote en esa estación"),
            "Máquinas": st.column_config.NumberColumn(min_value=1, step=1, help="Máquinas en paralelo"),
        },
    )

    st.markdown("### 2. Demanda del sistema")
    a, b = st.columns(2)
    cfg["lambda_h"] = a.number_input("Tasa de llegada λ (lotes/h)", min_value=0.01, value=float(cfg["lambda_h"]))
    cfg["phi_auto"] = b.checkbox("Calcular tiempo de flujo φ como suma de t0 (sin colas)", value=bool(cfg["phi_auto"]))
    if not cfg["phi_auto"]:
        cfg["phi_min"] = b.number_input("Tiempo de flujo φ (min)", min_value=0.0, value=float(cfg["phi_min"]))

    t = P["toc"].copy()
    t["Estación"] = t["Estación"].fillna("").astype(str)
    t["t0 (min/lote)"] = pd.to_numeric(t["t0 (min/lote)"], errors="coerce").fillna(0.0)
    t["Máquinas"] = pd.to_numeric(t["Máquinas"], errors="coerce").fillna(1).clip(lower=1)
    t = t[(t["Estación"] != "") & (t["t0 (min/lote)"] > 0)].reset_index(drop=True)

    if t.empty:
        st.info("Agrega al menos una estación con tiempo de proceso mayor a cero.")
        st.stop()

    t["Capacidad (lotes/h)"] = t["Máquinas"] * 60.0 / t["t0 (min/lote)"]
    cap_sistema = t["Capacidad (lotes/h)"].min()
    delta = min(cfg["lambda_h"], cap_sistema)  # throughput real
    t["Utilización (%)"] = delta * (t["t0 (min/lote)"] / 60.0) / t["Máquinas"] * 100
    i_bn = int(t["Utilización (%)"].idxmax())
    phi_h = (t["t0 (min/lote)"].sum() if cfg["phi_auto"] else cfg["phi_min"]) / 60.0
    wip = delta * phi_h

    st.markdown("### 3. Resultados")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Throughput δ", f"{delta:.2f} lotes/h")
    k2.metric("Capacidad máxima", f"{cap_sistema:.2f} lotes/h")
    k3.metric("Trabajo en proceso w = δ·φ", f"{wip:.2f} lotes")
    k4.metric("Cuello de botella", t.loc[i_bn, "Estación"])

    if cfg["lambda_h"] > cap_sistema:
        st.error(f"La llegada ({cfg['lambda_h']:.2f} lotes/h) supera la capacidad del sistema "
                 f"({cap_sistema:.2f}). Se acumularán lotes en {t.loc[i_bn, 'Estación']}.")
    else:
        st.success(f"El sistema absorbe la demanda. {t.loc[i_bn, 'Estación']} es la más cargada "
                   f"({t.loc[i_bn, 'Utilización (%)']:.1f} %).")

    colores = [ROJO if i == i_bn else GRIS for i in t.index]
    fig = go.Figure(go.Bar(x=t["Estación"], y=t["Utilización (%)"], marker_color=colores,
                           text=t["Utilización (%)"].round(1).astype(str) + " %", textposition="outside"))
    fig.add_hline(y=100, line_dash="dash", line_color=ROJO, annotation_text="Capacidad 100 %")
    fig.update_layout(title="Utilización por estación (cuello de botella en rojo)",
                      yaxis_title="%", plot_bgcolor="white", margin=dict(t=50))
    fig.update_yaxes(gridcolor=BORDE, range=[0, max(110, t["Utilización (%)"].max() * 1.15)])
    st.plotly_chart(fig)
    st.dataframe(t.style.format({"t0 (min/lote)": "{:.2f}", "Capacidad (lotes/h)": "{:.2f}",
                                 "Utilización (%)": "{:.1f}"}), hide_index=True)

# ==========================================================
# MÓDULO 5: COMSOAL
# ==========================================================
elif modulo == "5. Balanceo COMSOAL":
    st.title("Balanceo de línea estocástico (COMSOAL)")
    errores, avisos = validar(tc)
    for e in errores:
        st.error(e)
    if errores:
        st.stop()
    for a in avisos:
        st.warning(a)

    dur = {r["ID Tarea"]: float(r["Tiempo Estándar (s)"]) for _, r in tc.iterrows()}
    preds = {r["ID Tarea"]: parse_preds(r["Preds"]) for _, r in tc.iterrows()}
    t_total, t_max = sum(dur.values()), max(dur.values())

    st.markdown("### 1. Tiempo de ciclo")
    with st.expander("Calcular el tiempo de ciclo desde la demanda (takt time)"):
        d1, d2, d3 = st.columns(3)
        cfg["demanda"] = d1.number_input("Demanda por turno (unidades)", min_value=1, value=int(cfg["demanda"]))
        cfg["disponible_min"] = d2.number_input("Tiempo disponible por turno (min)", min_value=1.0,
                                                value=float(cfg["disponible_min"]))
        takt = cfg["disponible_min"] * 60 / cfg["demanda"]
        d3.metric("Takt time", f"{takt:.1f} s")

        def usar_takt():
            cfg["ciclo"] = round(float(takt), 2)
        st.button("Usar como tiempo de ciclo", on_click=usar_takt)

    c1, c2, c3 = st.columns(3)
    cfg["ciclo"] = c1.number_input("Tiempo de ciclo máximo C (s)", min_value=1.0, value=float(cfg["ciclo"]))
    cfg["iteraciones"] = c2.number_input("Iteraciones", min_value=100, max_value=100000,
                                         value=int(cfg["iteraciones"]), step=500)
    cfg["semilla"] = c3.number_input("Semilla aleatoria", min_value=0, value=int(cfg["semilla"]))
    C = float(cfg["ciclo"])

    n_min = math.ceil(t_total / C)
    p1, p2, p3 = st.columns(3)
    p1.metric("Tiempo total de tareas", f"{t_total:.1f} s")
    p2.metric("Mínimo teórico de estaciones", n_min)
    p3.metric("Tarea más larga", f"{t_max:.1f} s")

    if t_max > C:
        culpables = [t for t, v in dur.items() if v > C]
        st.error(f"C = {C:.1f} s es menor que la tarea más larga ({', '.join(culpables)}). "
                 f"Sube C a mínimo {t_max:.1f} s o divide esa tarea.")
        st.stop()

    firma = (tuple(dur.items()), tuple((k, tuple(v)) for k, v in preds.items()),
             C, int(cfg["iteraciones"]), int(cfg["semilla"]))

    if st.button("Ejecutar COMSOAL", type="primary"):
        with st.spinner("Buscando la mejor configuración..."):
            r = comsoal(dur, preds, C, cfg["iteraciones"], cfg["semilla"])
        r.update({"firma": firma, "dur": dur, "preds": preds, "C": C})
        st.session_state.res = r

    r = st.session_state.get("res")
    if not r:
        st.info("Ajusta los parámetros y pulsa **Ejecutar COMSOAL**.")
        st.stop()
    if r["firma"] != firma:
        st.warning("Cambiaron los datos o parámetros desde la última corrida. Vuelve a ejecutar para actualizar. "
                   "Abajo se muestra el resultado anterior.")
    dur, preds, C = r["dur"], r["preds"], r["C"]
    est = r["estaciones"]
    n = len(est)
    t_total = sum(dur.values())
    EL = t_total / (n * C) * 100
    RB = 100 - EL
    muerto = n * C - t_total

    st.markdown("---")
    st.markdown("### 2. Resultados")
    k = st.columns(5)
    k[0].metric("Estaciones", n, delta=f"mínimo teórico {math.ceil(t_total / C)}", delta_color="off")
    k[1].metric("Eficiencia de línea (EL)", f"{EL:.1f} %")
    k[2].metric("Retardo de balance (RB)", f"{RB:.1f} %")
    k[3].metric("Índice de suavidad (IS)", f"{r['IS']:.2f}")
    k[4].metric("Tiempo ocioso total", f"{muerto:.1f} s")

    paleta = px.colors.qualitative.Set3 + px.colors.qualitative.Pastel
    estacion_de = {t: i for i, e in enumerate(est) for t in e["tareas"]}
    color_est = {i: paleta[i % len(paleta)] for i in range(n)}
    i_cuello = int(np.argmax([e["tiempo"] for e in est]))

    st.markdown("### Carga por estación")
    fig = go.Figure()
    for i, e in enumerate(est):
        for t in e["tareas"]:
            fig.add_trace(go.Bar(
                x=[f"Est {i + 1}"], y=[dur[t]], name=t, text=t, textposition="inside",
                marker=dict(color=color_est[i], line=dict(color="white", width=1.5)),
                hovertemplate=f"<b>{t}</b><br>{dur[t]:.2f} s<extra></extra>", showlegend=False))
    fig.add_hline(y=C, line_dash="dash", line_color=ROJO, line_width=2, annotation_text=f"C = {C:g} s")
    fig.update_layout(barmode="stack", yaxis_title="Tiempo acumulado (s)", plot_bgcolor="white",
                      title="Ocupación de cada estación frente al tiempo de ciclo", margin=dict(t=50))
    fig.update_yaxes(gridcolor=BORDE, range=[0, C * 1.12])
    st.plotly_chart(fig)

    st.markdown("### Asignación de tareas")
    tabla = pd.DataFrame([{
        "Estación": f"Est {i + 1}", "Tareas": " → ".join(e["tareas"]), "Carga (s)": e["tiempo"],
        "Ocioso (s)": C - e["tiempo"], "Utilización (%)": e["tiempo"] / C * 100} for i, e in enumerate(est)])
    st.dataframe(tabla.style.format({"Carga (s)": "{:.1f}", "Ocioso (s)": "{:.1f}", "Utilización (%)": "{:.1f}"}),
                 hide_index=True)
    st.markdown(
        f"<div class='nota'>La estación más cargada es <b>Est {i_cuello + 1}</b> "
        f"({est[i_cuello]['tiempo']:.1f} s). Con la distribución actual la línea produce una unidad cada "
        f"<b>{est[i_cuello]['tiempo']:.1f} s</b> como máximo.</div>", unsafe_allow_html=True)

    st.markdown("### Diagrama de precedencias por estación")
    dot = graphviz.Digraph()
    dot.attr(rankdir="LR")
    dot.attr("node", style="rounded,filled", shape="box", fontname="Helvetica")
    for t, i in estacion_de.items():
        dot.node(t, f"{t}\n{dur[t]:.1f} s\nEst {i + 1}", fillcolor=color_est[i])
    for t, ps in preds.items():
        for p in ps:
            dot.edge(p, t)
    st.graphviz_chart(dot)

    with st.expander("Ver cómo se comportaron las iteraciones"):
        h = pd.DataFrame(r["historial"], columns=["Estaciones", "IS"])
        conteo = h["Estaciones"].value_counts().sort_index().reset_index()
        conteo.columns = ["Estaciones", "Soluciones"]
        conteo["Estaciones"] = conteo["Estaciones"].astype(str)
        figh = go.Figure(go.Bar(x=conteo["Estaciones"], y=conteo["Soluciones"],
                                marker_color=[ROJO if int(e) == n else GRIS for e in conteo["Estaciones"]]))
        figh.update_layout(title="Soluciones encontradas según número de estaciones",
                           xaxis_title="Estaciones", yaxis_title="Soluciones", plot_bgcolor="white")
        st.plotly_chart(figh)
        st.caption(f"{len(h)} iteraciones. En rojo, el número de estaciones de la mejor solución.")