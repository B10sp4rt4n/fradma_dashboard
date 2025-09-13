import streamlit as st
import pandas as pd
import numpy as np
from unidecode import unidecode
from io import BytesIO

# =============================================================================
# FUNCIONES UTILITARIAS
# =============================================================================

def format_currency(value):
    """Formatea un número como una cadena de moneda."""
    if pd.isna(value) or value is None:
        return "$0.00"
    return f"${value:,.2f}"

def normalizar_columnas(df):
    """Limpia y normaliza los nombres de las columnas de un DataFrame."""
    nuevas_columnas = []
    for col in df.columns:
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str)
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df

@st.cache_data
def to_excel(df):
    """Convierte un DataFrame a un archivo Excel en memoria para su descarga."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Deudas')
    processed_data = output.getvalue()
    return processed_data

# =============================================================================
# FUNCIONES DE PROCESAMIENTO DE DATOS
# =============================================================================

def cargar_y_limpiar_datos(xls):
    """Carga, une y limpia los datos de las hojas de Excel."""
    df_vigentes = pd.read_excel(xls, sheet_name='CXC VIGENTES')
    df_vencidas = pd.read_excel(xls, sheet_name='CXC VENCIDAS')

    df_vigentes = normalizar_columnas(df_vigentes)
    df_vencidas = normalizar_columnas(df_vencidas)

    for df in [df_vigentes, df_vencidas]:
        if 'cliente' in df.columns:
            df.rename(columns={'cliente': 'deudor'}, inplace=True)
            if 'razon_social' in df.columns:
                df.drop(columns=['razon_social'], inplace=True)
        elif 'razon_social' in df.columns:
            df.rename(columns={'razon_social': 'deudor'}, inplace=True)

        column_rename = {'saldo_usd': 'saldo_adeudado', 'vencimiento': 'fecha_vencimiento'}
        df.rename(columns=column_rename, inplace=True)

    df_vigentes['origen'] = 'VIGENTE'
    df_vencidas['origen'] = 'VENCIDA'

    common_cols = list(set(df_vigentes.columns) & set(df_vencidas.columns))
    df_deudas = pd.concat([df_vigentes[common_cols], df_vencidas[common_cols]], ignore_index=True)
    
    if 'saldo_adeudado' not in df_deudas.columns or 'deudor' not in df_deudas.columns:
        st.error("No se encontraron las columnas 'saldo_adeudado' o 'deudor' ('cliente'/'razon_social').")
        return None

    df_deudas['saldo_adeudado'] = pd.to_numeric(df_deudas['saldo_adeudado'], errors='coerce').fillna(0)
    return df_deudas

def calcular_antiguedad(df):
    """Calcula los días de vencimiento y asigna un nivel de riesgo."""
    if 'fecha_vencimiento' in df.columns:
        df['fecha_vencimiento'] = pd.to_datetime(df['fecha_vencimiento'], errors='coerce')
        df['dias_vencido'] = (pd.Timestamp.now() - df['fecha_vencimiento']).dt.days
        
        bins = [-np.inf, 0, 30, 60, 90, np.inf]
        labels = ['Al Corriente', '1-30 días', '31-60 días', '61-90 días', '>90 días']
        df['riesgo'] = pd.cut(df['dias_vencido'], bins=bins, labels=labels, right=False)
    return df

# =============================================================================
# FUNCIONES PARA RENDERIZAR COMPONENTES DE LA UI
# =============================================================================

def mostrar_kpis(total_adeudado, deuda_vencida):
    """Muestra los KPIs principales en la parte superior del dashboard."""
    porcentaje_vencido = (deuda_vencida / total_adeudado * 100) if total_adeudado > 0 else 0
    
    st.markdown("### Resumen General")
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Saldo Total", format_currency(total_adeudado))
    col2.metric("🔥 Saldo Vencido", format_currency(deuda_vencida))
    col3.metric("📈 % Vencido del Total", f"{porcentaje_vencido:.1f}%", delta_color="inverse")
    st.divider()

def mostrar_tab_riesgo(df_deudas, total_adeudado):
    """Muestra el contenido de la pestaña 'Análisis de Riesgo'."""
    st.subheader("Análisis de Riesgo por Antigüedad")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("###### 🔝 Top 5 Deudores")
        top_deudores = df_deudas.groupby('deudor')['saldo_adeudado'].sum().nlargest(5).reset_index()
        st.dataframe(top_deudores,
                     column_config={
                         "deudor": "Cliente",
                         "saldo_adeudado": st.column_config.NumberColumn("Saldo", format="$ {:,.2f}")
                     }, hide_index=True, use_container_width=True)

    with col2:
        st.markdown("###### 📊 Composición de la Deuda")
        if 'riesgo' in df_deudas.columns:
            riesgo_df = df_deudas.groupby('riesgo', observed=False)['saldo_adeudado'].sum()
            st.bar_chart(riesgo_df, color="#ff4b4b")
        else:
            st.info("No hay datos de antigüedad para graficar.")
            
def mostrar_tab_agente(df_deudas):
    """Muestra el contenido de la pestaña 'Análisis por Agente'."""
    st.subheader("Desempeño de Cartera por Agente")
    
    if 'vendedor' in df_deudas.columns and 'riesgo' in df_deudas.columns:
        agente_riesgo = df_deudas.groupby(['vendedor', 'riesgo'], observed=False)['saldo_adeudado'].sum().unstack(fill_value=0)
        agente_riesgo['Total'] = agente_riesgo.sum(axis=1)
        agente_riesgo.sort_values('Total', ascending=False, inplace=True)
        
        st.markdown("###### Saldo por Agente y Nivel de Riesgo")
        st.bar_chart(agente_riesgo.drop(columns='Total'))
        
        st.markdown("###### Tabla de Datos")
        st.dataframe(agente_riesgo.style.format(format_currency), use_container_width=True)
    else:
        st.info("No se encontraron las columnas 'vendedor' o 'fecha_vencimiento' para este análisis.")

def mostrar_tab_consulta(df_deudas):
    """Muestra el contenido de la pestaña 'Consulta por Cliente'."""
    st.subheader("Consulta Detallada por Cliente")
    
    deudores = sorted(df_deudas['deudor'].astype(str).unique().tolist())
    selected_deudor = st.selectbox("Selecciona un cliente para ver el detalle", deudores, index=None, placeholder="Escribe para buscar...")
    
    if selected_deudor:
        deudor_df = df_deudas[df_deudas['deudor'] == selected_deudor].copy()
        total_deudor = deudor_df['saldo_adeudado'].sum()
        
        st.metric(f"Saldo total de {selected_deudor}", format_currency(total_deudor))

        st.dataframe(deudor_df,
                     column_config={
                        "fecha_vencimiento": st.column_config.DateColumn("Vencimiento", format="DD/MM/YYYY"),
                        "saldo_adeudado": st.column_config.NumberColumn("Saldo", format="$ {:,.2f}"),
                        "dias_vencido": st.column_config.NumberColumn("Días Vencido"),
                        "origen": "Estado"
                     }, hide_index=True, use_container_width=True)

# =============================================================================
# FUNCIÓN PRINCIPAL DE EJECUCIÓN
# =============================================================================

def run(archivo):
    st.header("💳 Dashboard de Cartera por Cobrar (CxC)")

    if not archivo.name.endswith(('.xls', '.xlsx')):
        st.error("❌ Solo se aceptan archivos Excel para este módulo.")
        return

    with st.status("⚙️ Procesando archivo de cartera...", expanded=True) as status:
        try:
            xls = pd.ExcelFile(archivo)
            if "CXC VIGENTES" not in xls.sheet_names or "CXC VENCIDAS" not in xls.sheet_names:
                status.update(label="❌ No se encontraron las hojas 'CXC VIGENTES' y 'CXC VENCIDAS'.", state="error")
                return

            status.update(label="Cargando y limpiando datos...")
            df_deudas = cargar_y_limpiar_datos(xls)
            
            if df_deudas is None:
                raise ValueError("La carga de datos falló por falta de columnas clave.")

            status.update(label="Calculando antigüedad de deudas...")
            df_deudas = calcular_antiguedad(df_deudas)

            status.update(label="✅ ¡Procesamiento completado!", state="complete", expanded=False)

        except Exception as e:
            status.update(label=f"❌ Error crítico durante el procesamiento: {e}", state="error")
            return

    # --- KPIs y Navegación del Dashboard ---
    deuda_vencida = df_deudas[df_deudas['dias_vencido'] > 0]['saldo_adeudado'].sum() if 'dias_vencido' in df_deudas else 0
    mostrar_kpis(df_deudas['saldo_adeudado'].sum(), deuda_vencida)
    
    # --- Pestañas para una navegación simplificada ---
    tab1, tab2, tab3 = st.tabs(["📊 Análisis de Riesgo", "👤 Análisis por Agente", "🔍 Consulta por Cliente"])

    with tab1:
        mostrar_tab_riesgo(df_deudas, df_deudas['saldo_adeudado'].sum())

    with tab2:
        mostrar_tab_agente(df_deudas)
        
    with tab3:
        mostrar_tab_consulta(df_deudas)
    
    # --- Botón de Descarga General ---
    st.divider()
    st.download_button(
       label="📥 Descargar Reporte Completo en Excel",
       data=to_excel(df_deudas),
       file_name='reporte_consolidado_deudas.xlsx',
       mime='application/vnd.ms-excel'
    )