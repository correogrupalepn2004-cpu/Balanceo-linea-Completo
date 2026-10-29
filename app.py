import streamlit as st
import pandas as pd
import numpy as np
import graphviz
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import random
import datetime

# ==========================================
# CONFIGURACIÓN Y ESTÉTICA CORPORATIVA
# ==========================================
st.set_page_config(page_title="Sistema ERP/MES - Ingeniería de Producción", page_icon="🏭", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #f4f6f9; padding: 15px; border-radius: 8px; border-left: 5px solid #003366; }
    .css-1d391kg { background-color: #f8f9fa; }
    h1, h2, h3 { color: #003366; font-family: 'Arial', sans-serif; }
    .stButton>button { background-color: #003366; color: white; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# UTILIDADES: EXPORTACIÓN
# ==========================================
def to_excel(df, sheet_name="Reporte"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# ==========================================
# BARRA LATERAL: NAVEGACIÓN Y METADATOS
# ==========================================
with st.sidebar:
    # Espacio para el logo de la EPN (puedes reemplazar la URL con tu archivo local)
    st.image("https://upload.wikimedia.org/wikipedia/commons/8/8c/Escudo_de_la_Escuela_Politécnica_Nacional.png", width=150)
    st.markdown("### 📋 Datos del Analista")
    analista = st.text_input("Nombre Completo", "Ing. Producción")
    fecha = st.date_input("Fecha del Análisis", datetime.date.today())
    
    st.markdown("---")
    st.markdown("### 🚀 Módulos del Sistema")
    modulo = st.radio("Seleccione el entorno:", [
        "1. Ingeniería de Producto (BOM)", 
        "2. Estudio de Tiempos", 
        "3. Cursograma Analítico", 
        "4. Capacidad y Restricciones", 
        "5. Balanceo de Líneas"
    ])

# ==========================================
# MÓDULO 1: INGENIERÍA DE PRODUCTO (BOM)
# ==========================================
if modulo == "1. Ingeniería de Producto (BOM)":
    st.title("📦 Ingeniería de Producto y Lista de Materiales (BOM)")
    st.markdown("Diseño de empaque y cálculo de costos y mermas.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Carga de Planos")
        plano = st.file_uploader("Subir Plano Técnico (AutoCAD, PDF, PNG)", type=['png', 'jpg', 'pdf'])
        lote = st.number_input("Tamaño del Lote de Producción", min_value=1, value=5625)
    
    with col2:
        st.subheader("Lista de Materiales (Datos de Marcseal por defecto)")
        # Datos del caso de estudio
        df_bom_def = pd.DataFrame({
            "Código": ["200388", "200386", "200646", "200647", "201199"],
            "Descripción": ["ENVASE PLASTICO 250 ML", "TAPA PLASTICA FLIP TOP", "ETIQUETA FRONTAL", "CONTRAETIQUETA", "CAJA DE CARTON (x12)"],
            "Req. por Unidad": [1, 1, 1, 1, 1/12],
            "Cantidad Usada Real": [5630, 5630, 5830, 5700, 469],
            "Costo Unitario ($)": [0.13108, 0.10083, 0.02193, 0.02221, 0.25002]
        })
        df_bom = st.data_editor(df_bom_def, num_rows="dynamic", use_container_width=True)
        
        if st.button("Calcular Costos y Mermas"):
            df_bom["Req. Teórico Total"] = np.ceil(df_bom["Req. por Unidad"] * lote)
            df_bom["Merma (%)"] = ((df_bom["Cantidad Usada Real"] / df_bom["Req. Teórico Total"]) - 1) * 100
            df_bom["Costo Lote ($)"] = df_bom["Cantidad Usada Real"] * df_bom["Costo Unitario ($)"]
            
            st.dataframe(df_bom.style.format({"Merma (%)": "{:.2f}%", "Costo Lote ($)": "${:.2f}"}), use_container_width=True)
            
            c1, c2 = st.columns(2)
            costo_total = df_bom["Costo Lote ($)"].sum()
            c1.metric("Costo Total del Lote", f"${costo_total:,.2f}")
            c2.metric("Costo Unitario de Empaque", f"${costo_total/lote:,.4f}")
            
            st.download_button("📥 Exportar BOM a Excel", to_excel(df_bom, "BOM"), "BOM_Producto.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==========================================
# MÓDULO 2: ESTUDIO DE TIEMPOS
# ==========================================
elif modulo == "2. Estudio de Tiempos":
    st.title("⏱️ Estudio de Tiempos y Estandarización")
    st.markdown("Depuración de cronometrajes usando Método Westinghouse y Suplementos.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("1. Cronometraje Base")
        to = st.number_input("Tiempo Observado (Promedio min)", min_value=0.01, value=1.45, step=0.01)
        z_val = st.selectbox("Nivel de Confianza (Z)", [("90%", 1.645), ("95%", 1.96), ("99%", 2.576)], format_func=lambda x: x[0])
        error = st.number_input("Error Permitido (%)", min_value=1, value=5) / 100
    
    with col2:
        st.subheader("2. Valoración Westinghouse")
        habilidad = st.selectbox("Habilidad", [("Excelente", 0.10), ("Bueno", 0.05), ("Medio", 0.0), ("Malo", -0.05)], index=1)
        esfuerzo = st.selectbox("Esfuerzo", [("Excelente", 0.10), ("Bueno", 0.05), ("Medio", 0.0), ("Malo", -0.05)], index=2)
        condiciones = st.selectbox("Condiciones", [("Excelente", 0.06), ("Bueno", 0.02), ("Medio", 0.0), ("Malo", -0.03)], index=2)
        consistencia = st.selectbox("Consistencia", [("Excelente", 0.04), ("Bueno", 0.01), ("Medio", 0.0), ("Malo", -0.02)], index=2)
        factor_ritmo = 1 + habilidad[1] + esfuerzo[1] + condiciones[1] + consistencia[1]
    
    with col3:
        st.subheader("3. Suplementos (OIT)")
        fatiga_base = st.checkbox("Fatiga Base (4%)", value=True)
        nec_personales = st.checkbox("Necesidades Personales (5%)", value=True)
        trabajo_pie = st.checkbox("Trabajo de pie (2%)", value=True)
        monotonia = st.checkbox("Trabajo muy monótono (4%)", value=False)
        
        suplementos = 0
        if fatiga_base: suplementos += 0.04
        if nec_personales: suplementos += 0.05
        if trabajo_pie: suplementos += 0.02
        if monotonia: suplementos += 0.04

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    tiempo_normal = to * factor_ritmo
    tiempo_estandar = tiempo_normal * (1 + suplementos)
    
    c1.metric("Factor de Ritmo Total", f"{(factor_ritmo)*100:.1f}%")
    c2.metric("Tiempo Normal (TN)", f"{tiempo_normal:.3f} min")
    c3.metric("TIEMPO ESTÁNDAR (TS)", f"{tiempo_estandar:.3f} min", "Usar en Balanceo")

# ==========================================
# MÓDULO 3: CURSOGRAMA ANALÍTICO
# ==========================================
elif modulo == "3. Cursograma Analítico":
    st.title("📋 Cursograma Analítico y Therbligs")
    st.markdown("Clasificación de actividades y análisis de valor agregado.")
    
    df_curso_def = pd.DataFrame({
        "Operación": ["Inspeccionar envase", "Llenado de salsa", "Tapar frasco", "Transporte a etiquetadora", "Etiquetado", "Espera lote", "Empaque en caja"],
        "Símbolo": ["Inspección", "Operación", "Operación", "Transporte", "Operación", "Espera", "Operación"],
        "Tiempo (min)": [0.8, 7.0, 3.0, 0.5, 4.0, 15.0, 5.0],
        "Distancia (m)": [0, 0, 0, 8.5, 0, 0, 0]
    })
    
    df_curso = st.data_editor(df_curso_def, num_rows="dynamic", use_container_width=True)
    
    if st.button("Generar Análisis de Valor"):
        # Clasificar Valor Agregado
        df_curso["Valor"] = df_curso["Símbolo"].apply(lambda x: "Agrega Valor (VA)" if x == "Operación" else "No Agrega Valor (NVA)")
        
        col1, col2 = st.columns(2)
        with col1:
            fig_pie = px.pie(df_curso, values='Tiempo (min)', names='Símbolo', title='Distribución de Tiempos por Símbolo', color_discrete_sequence=px.colors.qualitative.Set1)
            st.plotly_chart(fig_pie, use_container_width=True)
        with col2:
            fig_bar = px.histogram(df_curso, x='Valor', y='Tiempo (min)', color='Valor', title='Análisis de Valor Agregado (Mudas)', text_auto=True)
            st.plotly_chart(fig_bar, use_container_width=True)
            
        st.download_button("📥 Exportar Cursograma a Excel", to_excel(df_curso, "Cursograma"), "Cursograma.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==========================================
# MÓDULO 4: CAPACIDAD Y RESTRICCIONES (TOC)
# ==========================================
elif modulo == "4. Capacidad y Restricciones":
    st.title("🏭 Análisis de Capacidad y Cuellos de Botella (TOC)")
    st.markdown("Aplicación de la Ley de Little y detección de restricciones del sistema.")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Parámetros del Sistema")
        tasa_llegada = st.number_input("Tasa de Llegada (λ - lotes/hora)", min_value=0.1, value=3.0)
    
    with c2:
        df_toc_def = pd.DataFrame({
            "Máquina/Área": ["Preparación", "Dosificadora", "Tapadora", "Etiquetadora", "Empacadora"],
            "Tiempo de Proceso (h/lote)": [0.2, 0.4, 0.3, 0.6, 0.3]
        })
        df_toc = st.data_editor(df_toc_def, num_rows="dynamic", use_container_width=True)
        
    if st.button("Evaluar Sistema (TOC)"):
        df_toc["Throughput (δ)"] = tasa_llegada # Simplificación de conservación de masa para línea serial
        df_toc["Trabajo en Proceso (w)"] = df_toc["Throughput (δ)"] * df_toc["Tiempo de Proceso (h/lote)"]
        df_toc["Utilización (%)"] = (df_toc["Throughput (δ)"] * df_toc["Tiempo de Proceso (h/lote)"]) * 100
        
        st.dataframe(df_toc.style.format({"Utilización (%)": "{:.1f}%", "Trabajo en Proceso (w)": "{:.2f} lotes"}), use_container_width=True)
        
        # Gráfico identificando Cuello de Botella
        max_util = df_toc["Utilización (%)"].max()
        df_toc["Color"] = df_toc["Utilización (%)"].apply(lambda x: "red" if x == max_util else "blue")
        
        fig_toc = go.Figure(data=[go.Bar(
            x=df_toc["Máquina/Área"], 
            y=df_toc["Utilización (%)"],
            marker_color=df_toc["Color"],
            text=df_toc["Utilización (%)"].apply(lambda x: f"{x:.1f}%"),
            textposition='auto'
        )])
        fig_toc.update_layout(title="Utilización por Máquina (Rojo = Cuello de Botella)", yaxis_title="Utilización (%)")
        st.plotly_chart(fig_toc, use_container_width=True)

# ==========================================
# MÓDULO 5: BALANCEO DE LÍNEAS AVANZADO
# ==========================================
elif modulo == "5. Balanceo de Líneas":
    st.title("⚖️ Balanceo de Líneas: RPP vs COMSOAL")
    st.markdown("Optimización matemática de estaciones de trabajo.")
    
    with st.sidebar:
        st.header("Algoritmo")
        metodo = st.radio("Seleccionar Método:", ["RPP (Heurístico Exacto)", "COMSOAL (Aleatorio Estocástico)"])
        tiempo_ciclo = st.number_input("Tiempo de Ciclo Máximo (min)", min_value=1.0, value=19.0)
        
    df_bal_def = pd.DataFrame({
        "ID Tarea": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
        "Duración": [3.0, 3.0, 4.0, 7.0, 5.0, 3.0, 6.0, 1.0, 4.0, 4.0, 8.0, 6.0],
        "Predecesores": ["", "", "", "1,2", "3", "4,5", "6", "6", "7", "6", "8", "9,10,11"]
    })
    
    st.subheader("Tabla de Tareas y Precedencias")
    df_bal = st.data_editor(df_bal_def, num_rows="dynamic", use_container_width=True)
    
    if st.button("Ejecutar Algoritmo de Balanceo", type="primary"):
        # 1. Preparación de Diccionarios
        tareas = df_bal['ID Tarea'].astype(str).tolist()
        duraciones = {str(row['ID Tarea']): float(row['Duración']) for _, row in df_bal.iterrows()}
        predecesores = {}
        for _, row in df_bal.iterrows():
            t = str(row['ID Tarea'])
            preds_raw = str(row['Predecesores']).replace(' ', '')
            predecesores[t] = [] if preds_raw in ['', 'nan', 'None'] else preds_raw.split(',')

        # 2. Dibujar Red Graphviz
        st.subheader("Red de Precedencias")
        dot = graphviz.Digraph(engine='dot')
        dot.attr(rankdir='LR')
        for t in tareas: dot.node(t, f"{t}\n({duraciones[t]}m)")
        for t, preds in predecesores.items():
            for p in preds: dot.edge(p, t)
        st.graphviz_chart(dot)

        estaciones = []
        # ================= LÓGICA RPP =================
        if metodo == "RPP (Heurístico Exacto)":
            sucesores = {t: [] for t in tareas}
            for t, preds in predecesores.items():
                for p in preds: sucesores[p].append(t)
            
            todos_sucesores = {}
            for t in tareas:
                visitados, stack = set(), [t]
                while stack:
                    curr = stack.pop()
                    for succ in sucesores[curr]:
                        if succ not in visitados:
                            visitados.add(succ)
                            stack.append(succ)
                todos_sucesores[t] = visitados
                
            rpi = {t: duraciones[t] + sum(duraciones[s] for s in todos_sucesores[t]) for t in tareas}
            tareas_ordenadas = sorted(tareas, key=lambda x: (rpi[x], duraciones[x]), reverse=True)
            
            estacion_actual, tiempo_est = [], 0.0
            tareas_asignadas = set()
            while len(tareas_asignadas) < len(tareas):
                asignado = False
                for t in tareas_ordenadas:
                    if t not in tareas_asignadas and all(p in tareas_asignadas for p in predecesores[t]):
                        if tiempo_est + duraciones[t] <= tiempo_ciclo:
                            estacion_actual.append(t)
                            tareas_asignadas.add(t)
                            tiempo_est += duraciones[t]
                            asignado = True
                            break
                if not asignado:
                    estaciones.append({"tareas": estacion_actual, "tiempo": tiempo_est})
                    estacion_actual, tiempo_est = [], 0.0
            if estacion_actual: estaciones.append({"tareas": estacion_actual, "tiempo": tiempo_est})

        # ================= LÓGICA COMSOAL =================
        else:
            min_estaciones = float('inf')
            mejor_solucion = []
            for _ in range(1000): # Iteraciones COMSOAL
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
                        chosen = random.choice(fitting) # La magia estocástica
                        current_est.append(chosen)
                        assigned.append(chosen)
                        unassigned.remove(chosen)
                        curr_time += duraciones[chosen]
                if current_est: temp_estaciones.append({"tareas": current_est, "tiempo": curr_time})
                
                if len(temp_estaciones) < min_estaciones:
                    min_estaciones = len(temp_estaciones)
                    estaciones = list(temp_estaciones)

        # 3. KPIs y Diagrama de Gantt
        st.subheader("Resultados del Balanceo")
        num_est = len(estaciones)
        tiempo_total = sum(duraciones.values())
        eficiencia = (tiempo_total / (num_est * tiempo_ciclo)) * 100
        retardo = 100 - eficiencia
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Número de Estaciones", num_est)
        c2.metric("Eficiencia de la Línea (EL)", f"{eficiencia:.1f}%")
        c3.metric("Retardo (% Tiempo Ocioso)", f"{retardo:.1f}%")
        
        # Crear datos para el Gantt (Diagrama de Tiempos)
        gantt_data = []
        for i, est in enumerate(estaciones):
            inicio = 0
            for t in est["tareas"]:
                gantt_data.append(dict(Estación=f"Estación {i+1}", Tarea=f"T{t}", Inicio=inicio, Fin=inicio+duraciones[t]))
                inicio += duraciones[t]
                
        df_gantt = pd.DataFrame(gantt_data)
        df_gantt['Inicio_dt'] = pd.to_datetime(df_gantt['Inicio'], unit='m', origin='2000-01-01')
        df_gantt['Fin_dt'] = pd.to_datetime(df_gantt['Fin'], unit='m', origin='2000-01-01')
        
        fig_gantt = px.timeline(df_gantt, x_start="Inicio_dt", x_end="Fin_dt", y="Estación", color="Tarea", title="Diagrama de Gantt (Ocupación por Estación)")
        fig_gantt.update_xaxes(tickformat="%M:%S") # Mostrar minutos y segundos
        st.plotly_chart(fig_gantt, use_container_width=True)