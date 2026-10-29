import streamlit as st
import pandas as pd
import numpy as np
import graphviz
import plotly.express as px
import plotly.graph_objects as go
import json
import datetime
import random
from io import BytesIO

# ==========================================
# 0. CONFIGURACIÓN Y ESTÉTICA CORPORATIVA
# ==========================================
st.set_page_config(page_title="Software MES - EPN", page_icon="🏭", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #ff4b4b; box-shadow: 1px 1px 5px rgba(0,0,0,0.1);}
    h1, h2, h3 { color: #1e3d59; font-family: 'Segoe UI', sans-serif; }
    .css-1d391kg { background-color: #f1f3f6; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. INICIALIZACIÓN DEL ESTADO (MEMORIA)
# ==========================================
if 'proyecto' not in st.session_state:
    st.session_state.proyecto = {
        "meta": {"institucion": "Escuela Politécnica Nacional", "autor": "", "producto": "", "fecha": str(datetime.date.today())},
        "bom": pd.DataFrame({"Código": ["P-01", "E-01"], "Descripción": ["Producto Base", "Empaque"], "Cant": [1, 1], "Unidad": ["u", "u"], "Tarea Destino": ["T1", "T2"]}),
        "tiempos": pd.DataFrame({"ID Tarea": ["T1", "T2"], "Descripción": ["Llenado", "Empacado"], "Preds": ["", "T1"], "Tiempo Observado (s)": [45.0, 20.0]}),
        "cursograma": pd.DataFrame({"ID Tarea": ["T1", "T2"], "Símbolo": ["Operación", "Operación"], "Distancia (m)": [0.0, 0.0]})
    }

def guardar_proyecto():
    # Convertir a dict para JSON
    data = {
        "meta": st.session_state.proyecto["meta"],
        "bom": st.session_state.proyecto["bom"].to_dict(orient="records"),
        "tiempos": st.session_state.proyecto["tiempos"].to_dict(orient="records"),
        "cursograma": st.session_state.proyecto["cursograma"].to_dict(orient="records")
    }
    return json.dumps(data)

def cargar_proyecto(file):
    data = json.load(file)
    st.session_state.proyecto["meta"] = data["meta"]
    st.session_state.proyecto["bom"] = pd.DataFrame(data["bom"])
    st.session_state.proyecto["tiempos"] = pd.DataFrame(data["tiempos"])
    st.session_state.proyecto["cursograma"] = pd.DataFrame(data["cursograma"])
    st.success("¡Proyecto cargado exitosamente!")

# ==========================================
# 2. BARRA LATERAL: CONTROL DE PROYECTO
# ==========================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/8/8c/Escudo_de_la_Escuela_Politécnica_Nacional.png", width=120)
    st.markdown("### 💾 Control de Proyecto")
    
    # Cargar Proyecto
    archivo_subido = st.file_uploader("Abrir Proyecto (.json)", type="json")
    if archivo_subido is not None:
        if st.button("Cargar Datos"): cargar_proyecto(archivo_subido)
    
    # Guardar Proyecto
    st.download_button(label="📥 Guardar Progreso", data=guardar_proyecto(), file_name="mi_proyecto_mes.json", mime="application/json")
    
    st.markdown("---")
    st.markdown("### 📋 Metadatos")
    st.session_state.proyecto["meta"]["institucion"] = st.text_input("Institución", st.session_state.proyecto["meta"]["institucion"])
    st.session_state.proyecto["meta"]["autor"] = st.text_input("Analista", st.session_state.proyecto["meta"]["autor"])
    st.session_state.proyecto["meta"]["producto"] = st.text_input("Producto", st.session_state.proyecto["meta"]["producto"])
    
    st.markdown("---")
    modulo = st.radio("📍 NAVEGACIÓN", ["1. BOM y Ensamble", "2. Estudio de Tiempos", "3. Cursograma y Valor", "4. Balanceo COMSOAL"])

# ==========================================
# MÓDULO 1: BOM Y ENSAMBLE
# ==========================================
if modulo == "1. BOM y Ensamble":
    st.title("📦 Lista de Materiales (BOM) y Ensamble")
    st.info("Define los materiales y especifica en qué Tarea se inyectan a la línea.")
    
    st.session_state.proyecto["bom"] = st.data_editor(st.session_state.proyecto["bom"], num_rows="dynamic", use_container_width=True)
    
    st.subheader("🌳 Diagrama de Inyección de Materiales")
    if st.button("Generar Diagrama Visual"):
        dot = graphviz.Digraph(engine='dot')
        dot.attr(rankdir='LR')
        dot.node("PROD", st.session_state.proyecto["meta"]["producto"], shape='folder', style='filled', fillcolor='#1e3d59', fontcolor='white')
        
        for idx, row in st.session_state.proyecto["bom"].iterrows():
            nodo_mat = f"{row['Código']}\n{row['Descripción']}"
            dot.node(nodo_mat, shape='box', style='filled', fillcolor='#f0f2f6')
            tarea = str(row['Tarea Destino'])
            if tarea != "" and tarea != "nan":
                dot.edge(nodo_mat, tarea, label=f" {row['Cant']} {row['Unidad']}")
                dot.edge(tarea, "PROD")
        st.graphviz_chart(dot)

# ==========================================
# MÓDULO 2: ESTUDIO DE TIEMPOS GLOBAL
# ==========================================
elif modulo == "2. Estudio de Tiempos":
    st.title("⏱️ Estudio de Tiempos Estandarizado")
    
    st.markdown("### 1. Parámetros Globales (Operador y Entorno)")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Sistema Westinghouse (Factor de Valoración - RF)**")
        habilidad = st.selectbox("Habilidad", [("Excelente", 0.10), ("Bueno", 0.05), ("Medio", 0.0), ("Malo", -0.05)], index=2)[1]
        esfuerzo = st.selectbox("Esfuerzo", [("Excelente", 0.10), ("Bueno", 0.05), ("Medio", 0.0), ("Malo", -0.05)], index=2)[1]
        condiciones = st.selectbox("Condiciones", [("Excelente", 0.06), ("Medio", 0.0), ("Malo", -0.03)], index=1)[1]
        consistencia = st.selectbox("Consistencia", [("Excelente", 0.04), ("Medio", 0.0), ("Malo", -0.02)], index=1)[1]
        rf_total = 1 + habilidad + esfuerzo + condiciones + consistencia
    
    with c2:
        st.write("**Suplementos (OIT - A)**")
        fatiga = st.checkbox("Fatiga Base (4%)", value=True)
        pers = st.checkbox("Necesidades Personales (5%)", value=True)
        pie = st.checkbox("Trabajo de Pie (2%)", value=True)
        suplementos = sum([0.04 if fatiga else 0, 0.05 if pers else 0, 0.02 if pie else 0])
        st.metric("Multiplicador Global de Tiempo Estándar", f"{(rf_total * (1 + suplementos)):.3f}")

    st.markdown("### 2. Tabla de Cronometraje")
    df_t = st.data_editor(st.session_state.proyecto["tiempos"], num_rows="dynamic", use_container_width=True)
    st.session_state.proyecto["tiempos"] = df_t
    
    # Cálculo en bloque
    df_t['Tiempo Normal (s)'] = df_t['Tiempo Observado (s)'] * rf_total
    df_t['Tiempo Estándar (s)'] = df_t['Tiempo Normal (s)'] * (1 + suplementos)
    st.dataframe(df_t.style.format({"Tiempo Normal (s)": "{:.2f}", "Tiempo Estándar (s)": "{:.2f}"}), use_container_width=True)

# ==========================================
# MÓDULO 3: CURSOGRAMA Y VALOR
# ==========================================
elif modulo == "3. Cursograma y Valor":
    st.title("📋 Cursograma Analítico Interactivo")
    
    # Sincronizar tareas desde Módulo 2
    tareas_basicas = st.session_state.proyecto["tiempos"][["ID Tarea", "Descripción", "Tiempo Estándar (s)"]]
    
    # Asegurar que el cursograma tenga las mismas tareas
    df_c = st.session_state.proyecto["cursograma"]
    if not df_c["ID Tarea"].equals(tareas_basicas["ID Tarea"]):
        df_c = pd.merge(tareas_basicas, df_c[["ID Tarea", "Símbolo", "Distancia (m)"]], on="ID Tarea", how="left")
        df_c["Símbolo"] = df_c["Símbolo"].fillna("Operación")
        df_c["Distancia (m)"] = df_c["Distancia (m)"].fillna(0.0)
        st.session_state.proyecto["cursograma"] = df_c

    st.markdown("### 1. Clasificación ASME")
    simbolos = ["Operación", "Inspección", "Transporte", "Espera", "Almacenaje"]
    df_c['Símbolo'] = pd.Categorical(df_c['Símbolo'], categories=simbolos)
    df_c = st.data_editor(df_c, num_rows="dynamic", use_container_width=True)
    st.session_state.proyecto["cursograma"] = df_c

    st.markdown("### 2. Dashboard de Valor (Mudas)")
    c1, c2 = st.columns(2)
    
    # Gráfico de Espagueti (Flujo Visual)
    with c1:
        mapa_y = {sym: i for i, sym in enumerate(simbolos)}
        df_c['Eje_X'] = df_c['Símbolo'].map(mapa_y)
        df_c['Eje_Y'] = range(len(df_c), 0, -1)
        
        fig_spag = go.Figure()
        fig_spag.add_trace(go.Scatter(x=df_c['Eje_X'], y=df_c['Eje_Y'], mode='lines+markers+text',
                                      text=df_c['ID Tarea'], textposition="top right",
                                      marker=dict(size=12, color='#1e3d59'), line=dict(color='gray', width=2)))
        fig_spag.update_layout(title="Diagrama de Flujo (Espagueti)", xaxis=dict(tickvals=list(mapa_y.values()), ticktext=list(mapa_y.keys())), yaxis=dict(showticklabels=False))
        st.plotly_chart(fig_spag, use_container_width=True)
        
    # Gráfico de Pareto / Donut
    with c2:
        df_c['Tipo Valor'] = df_c['Símbolo'].apply(lambda x: "Agrega Valor (VA)" if x == "Operación" else "No Agrega Valor (NVA)")
        resumen = df_c.groupby('Tipo Valor')['Tiempo Estándar (s)'].sum().reset_index()
        fig_pie = px.pie(resumen, values='Tiempo Estándar (s)', names='Tipo Valor', title='Distribución de Tiempo', hole=0.4, color='Tipo Valor', color_discrete_map={'Agrega Valor (VA)':'#2ca02c', 'No Agrega Valor (NVA)':'#d62728'})
        st.plotly_chart(fig_pie, use_container_width=True)

# ==========================================
# MÓDULO 4: BALANCEO COMSOAL
# ==========================================
elif modulo == "4. Balanceo COMSOAL":
    st.title("⚖️ Optimización Estocástica (COMSOAL)")
    
    # Preparar datos desde Módulo 2
    df_tareas = st.session_state.proyecto["tiempos"]
    
    c1, c2, c3 = st.columns(3)
    tiempo_ciclo = c1.number_input("Tiempo de Ciclo Máximo (s)", min_value=1.0, value=60.0)
    iteraciones = c2.number_input("Iteraciones COMSOAL", min_value=100, value=1000, step=100)
    semilla = c3.number_input("Semilla Aleatoria", min_value=1, value=42)
    
    if st.button("🚀 Ejecutar COMSOAL", type="primary", use_container_width=True):
        random.seed(semilla)
        tareas = df_tareas['ID Tarea'].astype(str).tolist()
        duraciones = {str(row['ID Tarea']): float(row['Tiempo Estándar (s)']) for _, row in df_tareas.iterrows()}
        
        predecesores = {}
        for _, row in df_tareas.iterrows():
            t = str(row['ID Tarea'])
            preds_raw = str(row['Preds']).replace(' ', '')
            predecesores[t] = [] if preds_raw in ['', 'nan', 'None'] else preds_raw.split(',')
        
        # Algoritmo COMSOAL
        mejor_solucion = []
        min_estaciones = float('inf')
        mejor_IS = float('inf')
        
        for _ in range(iteraciones):
            unassigned = list(tareas)
            assigned, temp_estaciones, current_est = [], [], []
            curr_time = 0.0
            
            while unassigned:
                available = [t for t in unassigned if all(p in assigned for p in predecesores[t])]
                fitting = [t for t in available if duraciones[t] <= (tiempo_ciclo - curr_time)]
                
                if not fitting:
                    temp_estaciones.append({"tareas": current_est, "tiempo": curr_time})
                    current_est, curr_time = [], 0.0
                else:
                    chosen = random.choice(fitting)
                    current_est.append(chosen)
                    assigned.append(chosen)
                    unassigned.remove(chosen)
                    curr_time += duraciones[chosen]
            if current_est: temp_estaciones.append({"tareas": current_est, "tiempo": curr_time})
            
            # Evaluar IS (Índice de Suavidad)
            IS = np.sqrt(sum((tiempo_ciclo - est["tiempo"])**2 for est in temp_estaciones))
            
            if len(temp_estaciones) < min_estaciones or (len(temp_estaciones) == min_estaciones and IS < mejor_IS):
                min_estaciones = len(temp_estaciones)
                mejor_IS = IS
                mejor_solucion = list(temp_estaciones)

        # KPIs
        num_est = len(mejor_solucion)
        tiempo_total = sum(duraciones.values())
        eficiencia = (tiempo_total / (num_est * tiempo_ciclo)) * 100
        tiempo_muerto = (num_est * tiempo_ciclo) - tiempo_total
        
        st.markdown("---")
        st.markdown("### 🏆 Dashboard de Resultados")
        col_k1, col_k2, col_k3, col_k4 = st.columns(4)
        col_k1.metric("Estaciones Requeridas", num_est)
        col_k2.metric("Eficiencia (E)", f"{eficiencia:.1f} %")
        col_k3.metric("Índice Suavidad (IS)", f"{mejor_IS:.2f}")
        col_k4.metric("Tiempo Muerto Total", f"{tiempo_muerto:.1f} s")
        
        # 1. Gráfico de Carga de Estaciones (Apilado con Límite)
        st.markdown("### 📊 Gráfico de Carga por Estación")
        gantt_data = []
        colores_estacion = px.colors.qualitative.Pastel
        color_map = {}
        
        for i, est in enumerate(mejor_solucion):
            color_est = colores_estacion[i % len(colores_estacion)]
            for t in est["tareas"]:
                gantt_data.append({"Estación": f"Est {i+1}", "Tarea": t, "Tiempo (s)": duraciones[t]})
                color_map[t] = color_est
                
        df_carga = pd.DataFrame(gantt_data)
        fig_carga = px.bar(df_carga, x="Estación", y="Tiempo (s)", color="Tarea", title="Ocupación de Estaciones vs Tiempo de Ciclo", text="Tarea")
        fig_carga.add_hline(y=tiempo_ciclo, line_dash="dash", line_color="red", annotation_text=f"Ciclo Máx: {tiempo_ciclo}s")
        fig_carga.update_layout(barmode='stack')
        st.plotly_chart(fig_carga, use_container_width=True)

        # 2. Diagrama de Precedencias Pintado por Estación
        st.markdown("### 🕸️ Diagrama de Precedencias Asignado")
        dot = graphviz.Digraph(engine='dot')
        dot.attr(rankdir='LR')
        dot.attr('node', style='filled', fontname='Helvetica')
        
        for t in tareas:
            color = color_map.get(t, '#ffffff')
            dot.node(t, f"{t}\n({duraciones[t]}s)", fillcolor=color)
            
        for t, preds in predecesores.items():
            for p in preds: dot.edge(p, t)
            
        st.graphviz_chart(dot)