import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import io
import numpy as np

def run(df):
    st.title("📊 Heatmap de Ventas por Línea de Negocio / Producto (Fuente: X AGENTE)")

    df = df.copy()
    df['mes_anio'] = df['fecha'].dt.strftime('%b-%Y')
    df['anio'] = df['fecha'].dt.year
    df['trimestre'] = df['fecha'].dt.to_period('Q').astype(str)

    # ✅ Detección flexible de columna
    posibles_columnas_linea = [
        "linea_de_negocio", "linea de negocio",
        "linea_producto", "línea producto", "linea producto",
        "linea_de_producto", "línea prodcucto","Línea Prodcucto"
    ]

    columna_linea = next((col for col in df.columns if col.lower().strip() in posibles_columnas_linea), None)

    if columna_linea is None:
        st.error("❌ No se encontró ninguna columna que parezca 'Línea de Negocio' o 'Línea Producto'.")
        st.write(f"Columnas disponibles: {df.columns.tolist()}")
        return

    with st.sidebar:
        st.header("⚙️ Opciones de análisis")

        periodo_tipo = st.selectbox(
            "🗓️ Tipo de periodo:",
            ["Mensual", "Trimestral", "Anual", "Rango Personalizado"]
        )

        mostrar_crecimiento = st.checkbox("📈 Mostrar % de crecimiento vs periodo anterior")

    if periodo_tipo == "Mensual":
        df['periodo'] = df['mes_anio']
        growth_lag = 12
    elif periodo_tipo == "Trimestral":
        df['periodo'] = df['trimestre']
        growth_lag = 4
    elif periodo_tipo == "Anual":
        df['periodo'] = df['anio'].astype(str)
        growth_lag = 1
    elif periodo_tipo == "Rango Personalizado":
        with st.sidebar:
            start_date = st.date_input("📅 Fecha inicio:", value=df['fecha'].min())
            end_date = st.date_input("📅 Fecha fin:", value=df['fecha'].max())
        df = df[(df['fecha'] >= pd.to_datetime(start_date)) & (df['fecha'] <= pd.to_datetime(end_date))]
        df['periodo'] = "Rango Personalizado"
        growth_lag = None

    pivot_table = df.pivot_table(
        index='periodo',
        columns=columna_linea,
        values='importe',
        aggfunc='sum',
        fill_value=0
    )

    lineas_disponibles = list(pivot_table.columns)
    periodos_disponibles = list(pivot_table.index)

    selected_lineas = st.multiselect(
        "📌 Selecciona las líneas de negocio:",
        lineas_disponibles,
        default=lineas_disponibles
    )

    selected_periodos = st.multiselect(
        "📅 Selecciona los periodos:",
        periodos_disponibles,
        default=periodos_disponibles
    )

    if selected_lineas and selected_periodos:
        df_filtered = pivot_table.loc[selected_periodos, selected_lineas]

        with st.sidebar:
            min_importe, max_importe = st.slider(
                "💰 Filtro por importe ($):",
                min_value=float(df_filtered.min().min()),
                max_value=float(df_filtered.max().max()),
                value=(float(df_filtered.min().min()), float(df_filtered.max().max()))
            )

            top_n = st.number_input(
                "🏅 Top N líneas de negocio:",
                min_value=1,
                max_value=len(selected_lineas),
                value=min(10, len(selected_lineas)),
                step=1
            )

        df_filtered = df_filtered.applymap(lambda x: x if min_importe <= x <= max_importe else np.nan)
        total_por_linea = df_filtered.sum(axis=0)
        top_lineas = total_por_linea.sort_values(ascending=False).head(top_n).index.tolist()
        df_filtered = df_filtered[top_lineas]

        annot_data = df_filtered.copy().astype(str)
        if mostrar_crecimiento and growth_lag:
            df_growth = df_filtered.copy()
            try:
                if periodo_tipo == "Mensual":
                    df_growth.index = pd.to_datetime(df_growth.index, format='%b-%Y', errors='coerce')
                elif periodo_tipo == "Trimestral":
                    df_growth.index = pd.PeriodIndex(df_growth.index, freq='Q')
                elif periodo_tipo == "Anual":
                    df_growth.index = pd.to_datetime(df_growth.index, format='%Y', errors='coerce')

                df_growth = df_growth.sort_index()
                growth_table = df_growth.pct_change(periods=growth_lag) * 100
                growth_table.index = df_filtered.index

                for row in annot_data.index:
                    for col in annot_data.columns:
                        val = df_filtered.loc[row, col]
                        growth = growth_table.loc[row, col] if growth_table is not None else np.nan
                        if pd.notna(val):
                            if pd.notna(growth):
                                annot_data.loc[row, col] = f"{val:,.0f}\n({growth:.1f}%)"
                            else:
                                annot_data.loc[row, col] = f"{val:,.0f}"

            except Exception as e:
                st.warning(f"⚠️ Error calculando crecimiento: {e}")
                annot_data = df_filtered.applymap(lambda x: f"{x:,.0f}")
        else:
            annot_data = df_filtered.applymap(lambda x: f"{x:,.0f}")

        fig, ax = plt.subplots(figsize=(max(10, len(top_lineas)*1.5), max(5, len(selected_periodos)*0.6)))
        sns.heatmap(
            df_filtered,
            annot=annot_data.values,
            fmt="",
            cmap="Blues",
            cbar_kws={'label': 'Importe ($)'},
            linewidths=0.5,
            linecolor='gray',
            ax=ax
        )
        ax.set_xlabel("Línea de Negocio", fontsize=12)
        ax.set_ylabel("Periodo", fontsize=12)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=10)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=10)
        plt.title(f"Heatmap de Ventas ({periodo_tipo})", fontsize=14, pad=20)
        plt.tight_layout()
        st.pyplot(fig)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_filtered.to_excel(writer, sheet_name='Heatmap_Filtrado')
        buffer.seek(0)

        st.download_button(
            label="📥 Descargar tabla filtrada como Excel",
            data=buffer.getvalue(),
            file_name="heatmap_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ) 
