import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import io
import numpy as np

# Configuración de moneda
CURRENCY = "$"

st.set_page_config(page_title="Heatmap de Ventas por Línea de Negocio", layout="wide")
st.title("📊 Heatmap de Ventas por Línea de Negocio (Fuente: X AGENTE)")

uploaded_file = st.file_uploader("📂 Sube el archivo Excel que contenga la hoja con datos", type=["xlsx"])

if uploaded_file is not None:
    try:
        # Leer las hojas disponibles
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names

        with st.sidebar:
            selected_sheet = st.selectbox("📑 Selecciona la hoja:", sheet_names)

        # Leer el archivo saltando las primeras 3 filas
        df = pd.read_excel(uploaded_file, sheet_name=selected_sheet, engine='openpyxl', skiprows=3)

        # Limpieza y normalización de nombres de columnas
        df.columns = df.columns.str.strip().str.lower().str.replace('á','a').str.replace('é','e')\
            .str.replace('í','i').str.replace('ó','o').str.replace('ú','u')

        # Mapeo de columnas origen a columnas estándar
        column_map = {
            'fecha': 'fecha',
            'linea prodcucto': 'linea de negocio',
            'valor mn': 'importe'
        }

        # Validación
        if not all(col in df.columns for col in column_map.keys()):
            st.error("❌ El archivo debe tener las columnas: Fecha, Línea Prodcucto y Valor MN.")
        else:
            df = df.rename(columns=column_map)

            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
            df = df.dropna(subset=['fecha'])
            df['mes_anio'] = df['fecha'].dt.strftime('%b-%Y')
            df['anio'] = df['fecha'].dt.year
            df['trimestre'] = df['fecha'].dt.to_period('Q').astype(str)

            # Crear columna periodo_id
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

            with st.sidebar:
                st.header("⚙️ Opciones de análisis")
                periodo_tipo = st.selectbox(
                    "🗓️ Tipo de periodo:",
                    ["Mensual", "Trimestral", "Anual", "Rango Personalizado"]
                )
                mostrar_crecimiento = st.checkbox("📈 Mostrar % de crecimiento vs periodo anterior")

            df['periodo_id'] = df.apply(lambda row: generar_periodo_id(row, periodo_tipo), axis=1)

            # Asignar columna periodo
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
                growth_lag = None

            # Crear etiqueta visible para el eje Y
            df['periodo_etiqueta'] = df['periodo_id'] + " - " + df['periodo']

            # Ordenar
            df = df.sort_values('periodo_id')

            # Debug: Relación periodo vs periodo_id
            st.subheader("🛠️ Relación de Periodos vs Periodo_ID (Debug)")
            st.dataframe(df[['periodo', 'periodo_id', 'periodo_etiqueta']].drop_duplicates().sort_values('periodo_id'))

            # Pivot con nuevo índice
            pivot_table = df.pivot_table(
                index='periodo_etiqueta',
                columns='linea de negocio',
                values='importe',
                aggfunc='sum',
                fill_value=0
            )

            # Filtros solo por línea de negocio
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
                        f"💰 Filtro por importe ({CURRENCY}):",
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

                # Formato de moneda
                def format_currency(value):
                    if pd.notna(value):
                        return f"${value:,.2f}"
                    else:
                        return ""

                annot_data = df_filtered.copy().astype(str)
                if mostrar_crecimiento and growth_lag:
                    df_growth = df_filtered.copy()
                    try:
                        if periodo_tipo == "Mensual":
                            df_growth.index = pd.to_datetime(df_growth.index.str.split(' - ').str[1], format='%b-%Y', errors='coerce')
                        elif periodo_tipo == "Trimestral":
                            df_growth.index = pd.PeriodIndex(df_growth.index.str.split(' - ').str[1], freq='Q')
                        elif periodo_tipo == "Anual":
                            df_growth.index = pd.to_datetime(df_growth.index.str.split(' - ').str[1], format='%Y', errors='coerce')

                        df_growth = df_growth.sort_index()
                        growth_table = df_growth.pct_change(periods=growth_lag) * 100
                        growth_table.index = df_filtered.index

                        for row in annot_data.index:
                            for col in annot_data.columns:
                                val = df_filtered.loc[row, col]
                                growth = growth_table.loc[row, col] if growth_table is not None else np.nan
                                if pd.notna(val):
                                    if pd.notna(growth):
                                        annot_data.loc[row, col] = f"{format_currency(val)}\n({growth:.1f}%)"
                                    else:
                                        annot_data.loc[row, col] = f"{format_currency(val)}"
                    except Exception as e:
                        st.warning(f"⚠️ Error calculando crecimiento: {e}")
                        annot_data = df_filtered.applymap(lambda x: format_currency(x))
                else:
                    annot_data = df_filtered.applymap(lambda x: format_currency(x))

                # Heatmap final
                fig, ax = plt.subplots(figsize=(max(10, len(top_lineas)*1.5), max(5, len(df_filtered.index)*0.6)))
                sns.heatmap(
                    df_filtered,
                    annot=annot_data.values,
                    fmt="",
                    cmap="Greens",  # Color verde
                    cbar_kws={'label': f'Importe ({CURRENCY})'},
                    linewidths=0.5,
                    linecolor='gray',
                    annot_kws={"fontsize": 8},  # Tamaño reducido de fuente
                    ax=ax
                )
                ax.set_xlabel("Línea de Negocio", fontsize=12)
                ax.set_ylabel("Periodo", fontsize=12)
                ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right', fontsize=10)
                ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=10)
                plt.title(f"Heatmap de Ventas ({periodo_tipo})", fontsize=14, pad=20)
                plt.tight_layout()
                st.pyplot(fig)

                # Exportación incluyendo metadata
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_filtered.to_excel(writer, sheet_name='Heatmap_Filtrado')
                    df[['periodo', 'periodo_id', 'periodo_etiqueta']].drop_duplicates().to_excel(writer, sheet_name='Metadata_periodo_id', index=False)
                buffer.seek(0)

                st.download_button(
                    label="📥 Descargar tabla filtrada como Excel",
                    data=buffer.getvalue(),
                    file_name="heatmap_filtrado.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
