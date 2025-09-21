import streamlit as st
import pandas as pd
from unidecode import unidecode
import traceback

# Importa los módulos para cada página del dashboard
from main import main_kpi, main_comparativo, heatmap_ventas, kpi_cpc

# Intenta importar un módulo opcional para ETL
try:
    from main import etl_ventas_items_ui
    HAS_ETL_UI = True
except ImportError:
    HAS_ETL_UI = False

st.set_page_config(layout="wide", page_title="Fradma Dashboard")

# =============================================================================
# FUNCIONES DE PROCESAMIENTO
# =============================================================================

def normalizar_columnas(df):
    """Limpia y estandariza los nombres de las columnas."""
    nuevas_columnas = []
    for col in df.columns:
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str)
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df

def detectar_y_cargar_archivo(archivo):
    """Carga un archivo Excel, detectando inteligentemente múltiples hojas o formato CONTPAQi."""
    xls = pd.ExcelFile(archivo)
    if len(xls.sheet_names) > 1 and "X AGENTE" in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name="X AGENTE")
    else:
        preview = pd.read_excel(xls, nrows=1, header=None)
        skiprows = 3 if "contpaqi" in str(preview.iloc[0, 0]).lower() else 0
        df = pd.read_excel(xls, skiprows=skiprows)
    return normalizar_columnas(df)

# =============================================================================
# INTERFAZ PRINCIPAL
# =============================================================================

# --- Barra Lateral ---
with st.sidebar:
    st.image("https://i.imgur.com/g2y8d6M.png", width=150)
    st.title("Panel de Navegación")
    archivo = st.file_uploader("📂 Sube tu archivo de ventas", type=["csv", "xlsx"])

# --- Pantalla de Bienvenida (si no hay archivo) ---
if not archivo:
    st.title("📊 Bienvenido al Dashboard de Análisis Fradma")
    st.subheader("Por favor, sube un archivo de ventas en la barra lateral para comenzar.")
    st.info("Esta herramienta te permitirá visualizar KPIs, comparar rendimientos y analizar la cartera de clientes.")
    st.stop()

# --- Procesamiento del Archivo Cargado ---
if "df" not in st.session_state or st.session_state.get("archivo_cargado") != archivo.name:
    with st.status("⚙️ Procesando archivo...", expanded=True) as status:
        try:
            if archivo.name.endswith(".csv"):
                df = pd.read_csv(archivo)
                df = normalizar_columnas(df)
            else:
                df = detectar_y_cargar_archivo(archivo)

            # --- LÓGICA MEJORADA PARA CREAR LA COLUMNA 'AÑO' ---
            # 1. Intentar estandarizar una columna de año si ya existe (más robusto)
            posibles_anos = {c.lower().replace(" ", ""): c for c in df.columns}
            for variante in ["ano", "anio", "año", "aã±o"]:
                if variante in posibles_anos:
                    df = df.rename(columns={posibles_anos[variante]: "año"})
                    break

            # 2. Si después de estandarizar, 'año' NO existe, créala a partir de 'fecha'.
            if "año" not in df.columns:
                if "fecha" in df.columns:
                    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
                    df.dropna(subset=['fecha'], inplace=True) # Eliminar filas con fechas inválidas
                    df['año'] = df['fecha'].dt.year
                else:
                    st.error("❌ No se encontró una columna 'año' o 'fecha' en el archivo. No se puede continuar.")
                    st.stop()

            # Estandarizar y limpiar columna de ventas
            columnas_ventas = ["valor_usd", "ventas_usd", "valor_mn", "importe"]
            columna_encontrada = next((col for col in columnas_ventas if col in df.columns), None)

            if not columna_encontrada:
                st.error("No se encontró una columna de ventas compatible (ej. 'valor_usd', 'importe').")
                st.stop()

            st.session_state["columna_ventas"] = columna_encontrada

            # Limpieza adicional de datos
            df[columna_encontrada] = (
                df[columna_encontrada]
                .astype(str)
                .str.strip()
                .str.replace(r'[$,\s]', '', regex=True)
            )
            df[columna_encontrada] = pd.to_numeric(df[columna_encontrada], errors='coerce').fillna(0)

            # Guardar en el estado de la sesión
            st.session_state["df"] = df
            st.session_state["archivo_excel"] = archivo
            st.session_state["archivo_cargado"] = archivo.name

            status.update(label="✅ ¡Archivo procesado con éxito!", state="complete", expanded=False)

        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")
            st.error(traceback.format_exc())
            st.stop()

# --- Selección de Año Base en la Barra Lateral ---
if "df" in st.session_state:
    df = st.session_state["df"]
    # Limpiar la columna 'año' antes de usarla
    df.dropna(subset=['año'], inplace=True)
    df['año'] = df['año'].astype(int)
    
    # Esta es la línea que antes causaba el error y ahora está protegida
    años_disponibles = sorted(df["año"].unique(), reverse=True)
    año_base = st.sidebar.selectbox("📅 Selecciona el año base", años_disponibles, help="Elige el año para comparar y analizar KPIs.")
    st.session_state["año_base"] = año_base

# --- Menú de Navegación ---
with st.sidebar:
    menu_items = ["📈 KPIs Generales", "📊 Comparativo Año vs Año", "🔥 Heatmap Ventas", "💳 KPI Cartera CxC"]
    if HAS_ETL_UI:
        menu_items.append("🧩 Consolidación")
    menu = st.radio("Selecciona un reporte:", menu_items, help="Elige el tipo de análisis que deseas visualizar.")
    st.sidebar.info(f"Año base seleccionado: **{st.session_state.get('año_base', 'N/A')}**")

# --- Renderizado de la Página Seleccionada ---
if "df" in st.session_state:
    if menu == "📈 KPIs Generales":
        main_kpi.run()
    elif menu == "📊 Comparativo Año vs Año":
        main_comparativo.run(st.session_state["df"], año_base=st.session_state["año_base"])
    elif menu == "🔥 Heatmap Ventas":
        heatmap_ventas.run(st.session_state["df"])
    elif menu == "💳 KPI Cartera CxC":
        kpi_cpc.run(st.session_state["archivo_excel"])
    elif menu == "🧩 Consolidación" and HAS_ETL_UI:
        etl_ventas_items_ui.run()