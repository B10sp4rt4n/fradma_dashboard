
import streamlit as st
import pandas as pd

def run():
    st.title("📈 KPIs Generales")

    if "df" not in st.session_state:
        st.warning("Primero debes cargar un archivo CSV o Excel en el menú lateral.")
        return

    df = st.session_state["df"].copy()

    # Asegurar compatibilidad: valor_usd = importe o ventas_usd
    if "valor_usd" not in df.columns:
        if "ventas_usd" in df.columns:
            df = df.rename(columns={"ventas_usd": "valor_usd"})
        elif "importe" in df.columns:
            df = df.rename(columns={"importe": "valor_usd"})

    if "valor_usd" not in df.columns:
        st.error("No se encontró la columna 'valor_usd', 'ventas_usd' ni 'importe'.")
        return

    # Aplicar tipo de cambio promedio por año
    tipos_cambio = {
        2018: 19.24,
        2019: 19.26,
        2020: 21.49,
        2021: 20.28,
        2022: 20.13,
        2023: 17.81,
        2024: 18.325,
        2025: 20.00
    }

    df["anio"] = pd.to_datetime(df["fecha"], errors="coerce").dt.year
    df["tipo_cambio"] = df["anio"].map(tipos_cambio).fillna(17.0)
    df["valor_mn_calc"] = df["valor_usd"] * df["tipo_cambio"]

    # Mostrar dimensiones generales
    st.subheader("Resumen General de Ventas")

    total_usd = df["valor_usd"].sum()
    total_mn = df["valor_mn_calc"].sum()
    total_operaciones = len(df)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Ventas USD", f"${total_usd:,.0f}")
    col2.metric("Total Ventas MN", f"${total_mn:,.0f}")
    col3.metric("Operaciones", f"{total_operaciones:,}")

    # Filtros opcionales
    st.subheader("Filtros por Agente")
    agentes = df["agente"].dropna().unique() if "agente" in df.columns else []
    linea_producto = df["linea_producto"].dropna().unique() if "linea_producto" in df.columns else []

    agente_sel = st.selectbox("Selecciona Agente (opcional):", ["Todos"] + list(agentes)) if len(agentes) > 0 else "Todos"
    linea_sel = st.selectbox("Selecciona Línea de Producto (opcional):", ["Todas"] + list(linea_producto)) if len(linea_producto) > 0 else "Todas"

    if agente_sel != "Todos" and "agente" in df.columns:
        df = df[df["agente"] == agente_sel]
    if linea_sel != "Todas" and "linea_producto" in df.columns:
        df = df[df["linea_producto"] == linea_sel]

    # KPIs filtrados
    st.subheader("KPIs Filtrados")
    total_filtrado_usd = df["valor_usd"].sum()
    total_filtrado_mn = df["valor_mn_calc"].sum()
    operaciones_filtradas = len(df)

    colf1, colf2, colf3 = st.columns(3)
    colf1.metric("Ventas USD (filtro)", f"${total_filtrado_usd:,.0f}")
    colf2.metric("Ventas MN (filtro)", f"${total_filtrado_mn:,.0f}")
    colf3.metric("Operaciones (filtro)", f"{operaciones_filtradas:,}")

    # Tabla de detalle
    st.subheader("Detalle de ventas")
    st.dataframe(df.sort_values("fecha", ascending=False).head(50))
