
import streamlit as st
import pandas as pd
import altair as alt

st.caption("Versión actualizada - Junio 2025")


def run(df):
    st.title("Comparativo de Ventas por Mes y Año")

    df.columns = df.columns.str.lower().str.strip()

    # Asegurar compatibilidad: valor_usd = importe o ventas_usd
    if "valor_usd" not in df.columns:
        if "valor usd" in df.columns:
            df = df.rename(columns={"valor usd": "valor_usd"})
        elif "ventas_usd" in df.columns:
            df = df.rename(columns={"ventas_usd": "valor_usd"})
        elif "importe" in df.columns:
            df = df.rename(columns={"importe": "valor_usd"})

    if "valor_usd" not in df.columns:
        st.error("No se encontró la columna 'valor_usd', 'valor usd', 'ventas_usd' ni 'importe'.")
        return

    if "anio" in df.columns:
        df = df.rename(columns={"anio": "año"})
    if "aã±o" in df.columns:
        df = df.rename(columns={"aã±o": "año"})

    if "fecha" in df.columns and ("año" not in df.columns or "mes" not in df.columns):
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df["año"] = df["fecha"].dt.year
        df["mes"] = df["fecha"].dt.month

    df["valor_usd"] = pd.to_numeric(df["valor_usd"], errors="coerce").fillna(0)

    # Agrupar y pivotear
    pivot_ventas = df.groupby(["año", "mes"], as_index=False)["valor_usd"].sum()
    tabla_fija = pivot_ventas.pivot(index="año", columns="mes", values="valor_usd").fillna(0)

    for mes in range(1, 13):
        if mes not in tabla_fija.columns:
            tabla_fija[mes] = 0
    tabla_fija = tabla_fija[sorted(tabla_fija.columns)]

    st.subheader("Ventas por Mes y Año (Tabla)")
    st.dataframe(tabla_fija, use_container_width=True)

    # Gráfico anual
    df_chart = tabla_fija.reset_index().melt(id_vars="año", var_name="mes", value_name="valor_usd")
    df_chart["mes"] = df_chart["mes"].astype(int)

    st.subheader("Gráfico de Ventas por Año")
    chart = alt.Chart(df_chart).mark_line(point=True).encode(
        x=alt.X("mes:O", title="Mes"),
        y=alt.Y("valor_usd:Q", title="Ventas USD"),
        color="año:N",
        tooltip=["año", "mes", "valor_usd"]
    ).properties(width=800, height=400)

    st.altair_chart(chart, use_container_width=True)

    # Comparativo Año vs Año
    st.subheader("📊 Comparativo Año vs Año")

    anios_disponibles = sorted(df["año"].dropna().unique())
    if len(anios_disponibles) >= 2:
        anio_1 = st.selectbox("Selecciona el primer año", anios_disponibles, index=0)
        anio_2 = st.selectbox("Selecciona el segundo año", anios_disponibles, index=1)

        df_y1 = pivot_ventas[pivot_ventas["año"] == anio_1].set_index("mes")["valor_usd"]
        df_y2 = pivot_ventas[pivot_ventas["año"] == anio_2].set_index("mes")["valor_usd"]

        comparativo = pd.DataFrame({
            f"{anio_1}": df_y1,
            f"{anio_2}": df_y2
        }).fillna(0)

        comparativo[f"{anio_1}"] = pd.to_numeric(comparativo[f"{anio_1}"], errors="coerce").fillna(0)
        comparativo[f"{anio_2}"] = pd.to_numeric(comparativo[f"{anio_2}"], errors="coerce").fillna(0)

        comparativo["Diferencia"] = comparativo[f"{anio_2}"] - comparativo[f"{anio_1}"]
        comparativo["% Variación"] = (
            (comparativo["Diferencia"] / comparativo[f"{anio_1}"].replace(0, pd.NA)) * 100
        ).round(2)

        st.dataframe(comparativo)

        st.subheader("📈 Gráfico Comparativo")
        comparativo_reset = comparativo.reset_index().melt(id_vars="mes", var_name="variable", value_name="valor")

        chart_comp = alt.Chart(comparativo_reset).mark_line(point=True).encode(
            x=alt.X("mes:O", title="Mes"),
            y=alt.Y("valor:Q", title="Ventas USD"),
            color="variable:N",
            tooltip=["mes", "variable", "valor"]
        ).properties(width=800, height=400)

        st.altair_chart(chart_comp, use_container_width=True)
    else:
        st.info("Se necesitan al menos dos años para comparar.")
