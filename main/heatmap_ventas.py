import streamlit as st
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import io
import unicodedata

def run(df):
    st.title("📊 Heatmap de Ventas (Entrada Genérica)")

    def clean_columns(columns):
        return (
            columns.astype(str)
            .str.strip()
            .str.lower()
            .map(lambda x: unicodedata.normalize('NFKD', x).encode('ascii', errors='ignore').decode('utf-8'))
        )

    def detectar_columna(df, posibles_nombres):
        for posible in posibles_nombres:
            for col in df.columns:
                if unicodedata.normalize('NFKD', col.lower().strip()).encode('ascii', errors='ignore').decode('utf-8') == unicodedata.normalize('NFKD', posible.lower().strip()).encode('ascii', errors='ignore').decode('utf-8'):
                    return col
        return None

    mapa_columnas = {
        "linea": ["linea_prodcucto", "linea_producto", "linea_de_negocio", "linea producto", "linea_de_producto"],
        "importe": ["valor_mn", "importe", "valor_usd", "valor mn"]
    }

    df.columns = clean_columns(df.columns)
    df['mes_anio'] = df['fecha'].dt.strftime('%b-%Y')
    df['anio'] = df['fecha'].dt.year
    df['trimestre'] = df['fecha'].dt.to_period('Q').astype(str)

    columna_linea = detectar_columna(df, mapa_columnas["linea"])
    columna_importe = detectar_columna(df, mapa_columnas["importe"])

    if columna_linea is None or columna_importe is None:
        st.error("❌ No se encontraron las columnas clave necesarias para 'línea' e 'importe'.")
        st.write(f"Columnas detectadas en tu archivo: {df.columns.tolist()}")
        return

    with st.sidebar:
        st.header("⚙️ Opciones de análisis")
        periodo_tipo = st.selectbox(
            "🗓️ Tipo de periodo:",
            ["Mensual", "Trimestral", "Anual", "Rango Personalizado"]
        )
        mostrar_crecimiento = st.checkbox("📈 Mostrar % de crecimiento vs periodo anterior")

    # ✅ Crear identificador secuencial absoluto (period_id) ANTES del pivot_table
    try:
        if periodo_tipo == "Mensual":
            df['period_order'] = pd.to_datetime(df['fecha']).dt.to_period('M')
        elif periodo_tipo == "Trimestral":
            df['period_order'] = pd.to_datetime(df['fecha']).dt.to_period('Q')
        elif periodo_tipo == "Anual":
            df['period_order'] = pd.to_datetime(df['fecha']).dt.to_period('Y')
        else:
            df['period_order'] = 'Custom'

        unique_periods = sorted(df['period_order'].unique())
        period_id_map = {str(period): idx for idx, period in enumerate(unique_periods, start=1)}
        df['period_id'] = df['period_order'].astype(str).map(period_id_map)
    except Exception as e:
        st.warning(f"⚠️ Error creando period_id absoluto: {e}")

    # Asignar el campo 'periodo' visible según el tipo
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
        values=columna_importe,
        aggfunc='sum',
        fill_value=0
    )

    # Recuperar period_id para cada periodo después del pivot
    period_id_series = df.drop_duplicates('periodo').set_index('periodo')['period_id']
    df_period_ids = period_id_series.reindex(pivot_table.index)

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
        nuevas_lineas = set()

        if mostrar_crecimiento and growth_lag:
            try:
                df_growth = df_filtered.copy()

                # ✅ Ordenar df_growth internamente por el verdadero period_id antes de pct_change
                if periodo_tipo != "Rango Personalizado" and df_period_ids is not None:
                    df_growth['period_id'] = df_period_ids.loc[df_filtered.index]
                    df_growth = df_growth.sort_values('period_id').drop(columns='period_id')

                if periodo_tipo == "Mensual":
                    df_growth.index = pd.to_datetime(df_growth.index, format='%b-%Y', errors='coerce')
                elif periodo_tipo == "Trimestral":
                    df_growth.index = pd.PeriodIndex(df_growth.index, freq='Q')
                elif periodo_tipo == "Anual":
                    df_growth.index = pd.to_datetime(df_growth.index, format='%Y', errors='coerce')

                growth_table = df_growth.pct_change(periods=growth_lag) * 100
                growth_table = growth_table.loc[df_filtered.index]

                nuevas_ventas = np.sum(np.isinf(growth_table.values))
                st.sidebar.markdown("### 🔔 Detección de Nuevas Ventas")
                if nuevas_ventas > 0:
                    st.sidebar.success(f"💡 {nuevas_ventas} nuevas ventas detectadas (antes en cero)")
                else:
                    st.sidebar.info("⚪ No se detectaron nuevas ventas en este rango.")

                for row in annot_data.index:
                    for col in annot_data.columns:
                        val = df_filtered.loc[row, col]
                        growth = growth_table.loc[row, col] if growth_table is not None else np.nan
                        if pd.notna(val):
                            if pd.notna(growth) and not np.isinf(growth):
                                annot_data.loc[row, col] = f"{val:,.0f}\n({growth:.1f}%)"
                            elif np.isinf(growth):
                                annot_data.loc[row, col] = "NEW"
                                nuevas_lineas.add(col)
                            else:
                                annot_data.loc[row, col] = f"{val:,.0f}"

                if nuevas_lineas:
                    st.markdown("### 🟢 Líneas de negocio con nuevas ventas:")
                    for linea in nuevas_lineas:
                        st.markdown(f"- {linea}")

            except Exception as e:
                st.warning(f"⚠️ Error calculando crecimiento: {e}")
                annot_data = df_filtered.applymap(lambda x: f"{x:,.0f}")
        else:
            annot_data = df_filtered.applymap(lambda x: f"{x:,.0f}")

        fig, ax = plt.subplots(figsize=(max(10, len(top_lineas)*1.5), max(5, len(selected_periodos)*0.6)))
        sns.heatmap(
            df_filtered,
            annot=False,
            fmt="",
            cmap="Blues",
            cbar_kws={'label': 'Importe ($)'},
            linewidths=0.5,
            linecolor='gray',
            ax=ax
        )

        for i in range(len(df_filtered.index)):
            for j in range(len(df_filtered.columns)):
                text = annot_data.iloc[i, j]
                color = 'lime' if text == "NEW" else 'black'
                ax.text(
                    j + 0.5, i + 0.5, text,
                    ha='center', va='center',
                    color=color,
                    fontsize=9
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
