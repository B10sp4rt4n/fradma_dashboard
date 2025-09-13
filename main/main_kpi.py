import streamlit as st
import pandas as pd
import altair as alt

# main/main_kpi.py necesita usar algo de kpi_engine.py
from . import kpi_engine # El punto '.' significa "desde esta misma carpeta"

def run():
    st.title("📈 KPIs Generales")

    if "df" not in st.session_state:
        st.warning("Primero debes cargar un archivo CSV o Excel en el menú lateral.")
        return

    df = st.session_state["df"].copy()

    # ===================== INICIO DE LA CORRECCIÓN =====================

    # CORRECCIÓN 1: Convertir columnas con tipos de datos mixtos a string.
    # Esto soluciona los errores 'pyarrow.lib.ArrowTypeError' y 'pyarrow.lib.ArrowInvalid'
    # que ocurren cuando Streamlit intenta mostrar un DataFrame con columnas
    # que contienen, por ejemplo, tanto números como texto (ej. 'zona', 'r-factura').
    # También previene el 'TypeError' al intentar ordenar columnas con tipos incompatibles.
    for col in df.select_dtypes(include=['object']).columns:
        try:
            df[col] = df[col].astype(str)
        except Exception as e:
            st.warning(f"No se pudo convertir la columna '{col}' a string: {e}")

    # CORRECCIÓN 2: Asegurar que la columna de fecha sea de tipo datetime.
    # Se usa 'errors="coerce"' para convertir fechas no válidas en NaT (Not a Time).
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    else:
        st.error("El DataFrame debe contener una columna 'fecha'.")
        return

    # ===================== FIN DE LA CORRECCIÓN =======================

    # Asegurar compatibilidad: valor_usd = ventas_usd_con_iva o ventas_usd
    if "valor_usd" not in df.columns:
        if "ventas_usd" in df.columns:
            df = df.rename(columns={"ventas_usd": "valor_usd"})
        elif "ventas_usd_con_iva" in df.columns:
            df = df.rename(columns={"ventas_usd_con_iva": "valor_usd"})

    if "valor_usd" not in df.columns:
        st.error("No se encontró la columna 'valor_usd', 'ventas_usd' ni 'ventas_usd_con_iva'.")
        return

    # Aplicar tipo de cambio promedio por año
    tipos_cambio = {
        2018: 19.24, 2019: 19.26, 2020: 21.49, 2021: 20.28,
        2022: 20.13, 2023: 17.81, 2024: 18.325, 2025: 20.00
    }

    df["anio"] = df["fecha"].dt.year
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

    # === Filtros opcionales ===
    st.subheader("Filtros por Ejecutivo")

    # Buscar dinámicamente si la columna se llama 'agente', 'vendedor' o 'ejecutivo'
    columna_agente = None
    for col in df.columns:
        if col.lower() in ["agente", "vendedor", "ejecutivo"]:
            columna_agente = col
            break

    if columna_agente:
        # La conversión a string ya se hizo arriba, pero lo reforzamos aquí
        df["agente"] = df[columna_agente].astype(str)
        agentes = sorted(df["agente"].dropna().unique())
        agente_sel = st.selectbox("Selecciona Ejecutivo:", ["Todos"] + agentes)

        if agente_sel != "Todos":
            df = df[df["agente"] == agente_sel]
    else:
        st.warning("⚠️ No se encontró columna 'agente', 'vendedor' o 'ejecutivo'.")

    # Filtro adicional: línea de producto
    if "linea_producto" in df.columns:
        linea_producto = sorted(df["linea_producto"].dropna().unique())
        linea_sel = st.selectbox("Selecciona Línea de Producto (opcional):", ["Todas"] + list(linea_producto))

        if linea_sel != "Todas":
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

    # Ranking de vendedores
    if "agente" in df.columns:
        st.subheader("🏆 Ranking de Vendedores")

        ranking = (
            df.groupby("agente")
            .agg(total_usd=("valor_usd", "sum"), total_mn=("valor_mn_calc", "sum"), operaciones=("valor_usd", "count"))
            .sort_values("total_usd", ascending=False)
            .reset_index()
        )

        ranking.insert(0, "Ranking", range(1, len(ranking) + 1))
        st.dataframe(ranking.style.format({
            "total_usd": "${:,.0f}",
            "total_mn": "${:,.0f}",
            "operaciones": "{:,}"
        }))

    # Gráficos por agente
    if "agente" in df.columns and not df.empty:
        st.subheader("📊 Visualización de Ventas por Vendedor")

        chart_type = st.selectbox(
            "Selecciona tipo de gráfico:",
            ["Pie Chart", "Barras Horizontales", "Ventas por Año"]
        )

        df_chart = df[["agente", "anio", "valor_usd"]].dropna()
        resumen_agente = df_chart.groupby("agente").agg(total_ventas=("valor_usd", "sum")).reset_index()

        if chart_type == "Pie Chart":
            chart = alt.Chart(resumen_agente).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="total_ventas", type="quantitative"),
                color=alt.Color(field="agente", type="nominal"),
                tooltip=["agente", alt.Tooltip("total_ventas", title="Ventas (USD)", format="$,.2f")]
            ).properties(title="Participación de Vendedores (USD)")

        elif chart_type == "Barras Horizontales":
            chart = alt.Chart(resumen_agente).mark_bar().encode(
                x=alt.X("total_ventas:Q", title="Ventas Totales (USD)"),
                y=alt.Y("agente:N", sort="-x", title="Vendedor"),
                tooltip=["agente", alt.Tooltip("total_ventas", title="Ventas (USD)", format="$,.2f")]
            ).properties(title="Ventas Totales por Vendedor (USD)")

        elif chart_type == "Ventas por Año":
            resumen_anio_agente = df_chart.groupby(["anio", "agente"]).agg(total_ventas=("valor_usd", "sum")).reset_index()
            chart = alt.Chart(resumen_anio_agente).mark_bar().encode(
                x=alt.X("anio:N", title="Año"),
                y=alt.Y("total_ventas:Q", title="Ventas (USD)"),
                color="agente:N",
                tooltip=["anio", "agente", alt.Tooltip("total_ventas", title="Ventas (USD)", format="$,.2f")]
            ).properties(title="Ventas por Vendedor en el Tiempo")

        st.altair_chart(chart, use_container_width=True)