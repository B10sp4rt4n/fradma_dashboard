import streamlit as st
import pandas as pd
from main import main_kpi, main_comparativo #, main_lineas_producto

st.set_page_config(layout="wide")

archivo = st.sidebar.file_uploader("📂 Sube archivo CSV de ventas", type=["csv"])

if archivo:
    df = pd.read_csv(archivo)
    
    # Normaliza columnas
    df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    st.session_state["df"] = df


menu = st.sidebar.radio("Navegación", [
    "📈 KPIs Generales",
    "📊 Comparativo Año vs Año",
    "📦 Tablero Estilo Excel"
])

if menu == "📈 KPIs Generales":
    main_kpi.run()

elif menu == "📊 Comparativo Año vs Año":
    if "df" in st.session_state:
        main_comparativo.run(st.session_state["df"])

    else:
        st.warning("⚠️ Primero sube un archivo para visualizar el comparativo año vs año.")

#elif menu == "📦 Tablero Estilo Excel":
 ##   if "df" in st.session_state:
 #            main_lineas_producto.run(st.session_state["df"])
  #  else:
        st.warning("⚠️ Primero sube un archivo para ver el tablero estilo Excel.")

