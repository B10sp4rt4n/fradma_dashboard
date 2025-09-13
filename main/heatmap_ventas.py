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

    def generar_periodo_id(row, periodo_tipo):
        year_short = str(row['anio'])[-2:]
        month_num = row['fecha'].month
        trimestre = (month_num - 1) // 3 + 1

        if periodo_tipo == "Mensual":
            return f"{year_short}.{month_num:02d}"
        elif periodo_tipo == "Trimestral":
            return f"{year_short}.Q{trimestre}"
        elif periodo_tipo == "Anual":
            return f"{year_short}"
        else:
            return f"{year_short}.{month_num:02d}"

    df['periodo_id'] = df.apply(lambda row: generar_periodo_id(row, periodo_tipo), axis=1)

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

    df['periodo_etiqueta'] = df['periodo_id'] + " - " + df['periodo']
    df = df.sort_values('periodo_id')

    pivot_table = df.pivot_table(
        index='periodo_etiqueta',
        columns=columna_linea,
        values=columna_importe,
        aggfunc='sum',
        fill_value=0
    )

    period_id_lookup = df.drop_duplicates('periodo_etiqueta').set_index('periodo_etiqueta')['periodo_id']
    df_period_ids = period_id_lookup.reindex(pivot_table.index)

    lineas_disponibles = list(pivot_table.columns)

    selected_lineas = st.multiselect(
        "📌 Selecciona las líneas de negocio:",
        lineas_disponibles,
        default=lineas_disponibles
    )

    if selected_lineas:
        df_filtered = pivot_table.loc[:, selected_lineas]

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

        df_filtered = df_filtered.map(lambda x: x if min_importe <= x <= max_importe else np.nan)
        total_por_linea = df_filtered.sum(axis=0)
        top_lineas = total_por_linea.sort_values(ascending=False).head(top_n).index.tolist()
        df_filtered = df_filtered[top_lineas]

        def format_currency(value):
            if pd.notna(value):
                return f"${value:,.2f}"
            else:
                return ""

        annot_data = df_filtered.copy().astype(str)
        nuevas_lineas = set()

        if mostrar_crecimiento and growth_lag:
            try:
                df_growth = df_filtered.copy()
                df_growth['periodo_id_num'] = df_period_ids.loc[df_filtered.index].astype(float)
                df_growth = df_growth.sort_values('periodo_id_num').drop(columns='periodo_id_num')

                if periodo_tipo == "Mensual":
                    df_growth['periodo_base'] = [x.split(' - ')[1][:3] for x in df_growth.index]
                elif periodo_tipo == "Trimestral":
                    df_growth['periodo_base'] = [x.split(' - ')[1] for x in df_growth.index]
                    df_growth['periodo_base'] = df_growth['periodo_base'].str.extract(r'(Q[1-4])')
                elif periodo_tipo == "Anual":
                    df_growth['periodo_base'] = [x.split(' - ')[1] for x in df_growth.index]
                else:
                    df_growth['periodo_base'] = np.nan

                if periodo_tipo != "Rango Personalizado":
                    growth_table = df_growth.groupby('periodo_base').pct_change(periods=1) * 100
                    growth_table = growth_table.loc[:, df_filtered.columns]
                else:
                    growth_table = None

                for row in annot_data.index:
                    for col in annot_data.columns:
                        val = df_filtered.loc[row, col]
                        growth = growth_table.loc[row, col] if growth_table is not None else np.nan
                        if pd.notna(val):
                            if pd.notna(growth) and not np.isinf(growth):
                                annot_data.loc[row, col] = f"{format_currency(val)}\n({growth:.1f}%)"
                            elif np.isinf(growth):
                                annot_data.loc[row, col] = "NEW"
                                nuevas_lineas.add(col)
                            else:
                                annot_data.loc[row, col] = f"{format_currency(val)}"

                if nuevas_lineas:
                    st.markdown("### 🟢 Líneas de negocio con nuevas ventas:")
                    for linea in nuevas_lineas:
                        st.markdown(f"- {linea}")

            except Exception as e:
                st.warning(f"⚠️ Error calculando crecimiento YoY: {e}")
                annot_data = df_filtered.applymap(lambda x: format_currency(x))
        else:
            # DESPUÉS
            annot_data = df_filtered.map(lambda x: format_currency(x))

        fig, ax = plt.subplots(figsize=(max(10, len(top_lineas)*1.5), max(5, len(df_filtered.index)*0.6)))
        sns.heatmap(
            df_filtered,
            annot=False,
            fmt="",
            cmap="Greens",
            cbar_kws={'label': 'Importe ($)'},
            linewidths=0.5,
            linecolor='gray',
            ax=ax
        )

        norm = plt.Normalize(vmin=df_filtered.min().min(), vmax=df_filtered.max().max())

        for i in range(len(df_filtered.index)):
            for j in range(len(df_filtered.columns)):
                value = df_filtered.iloc[i, j]
                text = annot_data.iloc[i, j]

                if pd.notna(value):
                    intensity = norm(value)
                    if text == "NEW":
                        text_color = 'lime'
                    elif intensity > 0.6:
                        text_color = 'white'
                    else:
                        text_color = 'black'

                    ax.text(
                        j + 0.5, i + 0.5, text,
                        ha='center', va='center',
                        color=text_color,
                        fontsize=8
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
