import streamlit as st
import pandas as pd
from unidecode import unidecode
from main import main_kpi, main_comparativo, heatmap_ventas

st.set_page_config(layout="wide")

# 🛠️ FUNCIÓN: Normalización de encabezados
def normalizar_columnas(df):
    nuevas_columnas = []
    for col in df.columns:
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str)
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df

# 🛠️ FUNCIÓN: Carga de Excel con detección de múltiples hojas y CONTPAQi
def detectar_y_cargar_archivo(archivo):
    xls = pd.ExcelFile(archivo)
    hojas = xls.sheet_names

    # Caso 1: Si hay múltiples hojas → Forzar lectura de "X AGENTE"
    if len(hojas) > 1:
        if "X AGENTE" in hojas:
            hoja = "X AGENTE"
            st.info(f"📌 Archivo con múltiples hojas detectado. Leyendo hoja 'X AGENTE'.")
        else:
            st.warning("⚠️ Múltiples hojas detectadas pero no se encontró la hoja 'X AGENTE'. Selecciona manualmente.")
            hoja = st.sidebar.selectbox("📄 Selecciona la hoja a leer", hojas)
        df = pd.read_excel(xls, sheet_name=hoja)
        df = normalizar_columnas(df)

        with st.expander("🛠️ Debug - Columnas leídas desde X AGENTE"):
            st.write(df.columns.tolist())

        # Generación virtual de columnas año y mes para X AGENTE
        if hoja == "X AGENTE":
            if "fecha" in df.columns:
                try:
                    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
                    df["año"] = df["fecha"].dt.year
                    df["mes"] = df["fecha"].dt.month
                    st.success("✅ Columnas virtuales 'año' y 'mes' generadas correctamente desde 'fecha' en X AGENTE.")
                except Exception as e:
                    st.error(f"❌ Error al procesar la columna 'fecha' en X AGENTE: {e}")
            else:
                st.error("❌ No existe columna 'fecha' en X AGENTE para poder generar 'año' y 'mes'.")

    else:
        # Caso 2: Solo una hoja → Detectar si es CONTPAQi
        hoja = hojas[0]
        st.info(f"✅ Solo una hoja encontrada: **{hoja}**. Procediendo con detección CONTPAQi.")
        preview = pd.read_excel(xls, sheet_name=hoja, nrows=5, header=None)
        contiene_contpaqi = preview.iloc[0, 0]
        skiprows = 3 if isinstance(contiene_contpaqi, str) and "contpaqi" in contiene_contpaqi.lower() else 0
        if skiprows:
            st.info("📌 Archivo CONTPAQi detectado. Saltando primeras 3 filas.")
        df = pd.read_excel(xls, sheet_name=hoja, skiprows=skiprows)
        df = normalizar_columnas(df)

    return df

archivo = st.sidebar.file_uploader("📂 Sube archivo de ventas (.csv o .xlsx)", type=["csv", "xlsx"])

if archivo:
    if archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
        df = normalizar_columnas(df)
    else:
        df = detectar_y_cargar_archivo(archivo)

    # Detectar y renombrar columna de año
    for col in df.columns:
        if col in ["ano", "anio", "año", "aÃ±o", "aã±o"]:
            df = df.rename(columns={col: "año"})
            break

    if "año" in df.columns:
        df["año"] = pd.to_numeric(df["año"], errors="coerce")

    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype(str)

    columnas_ventas_usd = ["valor_usd", "ventas_usd", "ventas_usd_con_iva"]
    columna_encontrada = next((col for col in columnas_ventas_usd if col in df.columns), None)

    if not columna_encontrada:
        st.warning("⚠️ No se encontró la columna 'valor_usd', 'ventas_usd' ni 'ventas_usd_con_iva'.")
        st.write("Columnas detectadas:")
        st.write(df.columns.tolist())
    else:
        st.success(f"✅ Columna de ventas detectada: **{columna_encontrada}**")

    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    st.session_state["df"] = df
    st.session_state["archivo_path"] = archivo

    if "año" in df.columns:
        with st.expander("🛠️ Diagnóstico de columnas (debug)"):
            st.write("Columnas detectadas:", df.columns.tolist())
            st.write("Valores únicos en columna 'año':", df["año"].unique())

        años_disponibles = sorted(df["año"].dropna().unique())
        año_base = st.sidebar.selectbox("📅 Selecciona el año base", años_disponibles)
        st.session_state["año_base"] = año_base
        st.success(f"📌 Año base seleccionado: {año_base}")
    else:
        st.warning("⚠️ No se encontró columna 'año' para seleccionar año base.")

menu = st.sidebar.radio("Navegación", [
    "📈 KPIs Generales",
    "📊 Comparativo Año vs Año",
    "🔥 Heatmap Ventas"
])

if menu == "📈 KPIs Generales":
    main_kpi.run()

elif menu == "📊 Comparativo Año vs Año":
    if "df" in st.session_state:
        año_base = st.session_state.get("año_base", None)
        main_comparativo.run(st.session_state["df"], año_base=año_base)
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el comparativo año vs año.")

elif menu == "🔥 Heatmap Ventas":
    if "df" in st.session_state:
        heatmap_ventas.run(st.session_state["df"]) 
    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el Heatmap.")
