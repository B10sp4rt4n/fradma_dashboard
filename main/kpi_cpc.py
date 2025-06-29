import streamlit as st
import pandas as pd
import numpy as np
from unidecode import unidecode
from datetime import datetime

# 🛠️ FUNCIÓN: Normalización de encabezados (consistente con app.py)
def normalizar_columnas(df):
    nuevas_columnas = []
    for col in df.columns:
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str)
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df

def run(archivo):
    if not archivo.name.endswith(('.xls', '.xlsx')):
        st.error("❌ Solo se aceptan archivos Excel para el KPI CxC.")
        return

    try:
        xls = pd.ExcelFile(archivo)
        hojas = xls.sheet_names
        
        if "CXC VIGENTES" not in hojas or "CXC VENCIDAS" not in hojas:
            st.error("❌ No se encontraron ambas hojas necesarias: 'CXC VIGENTES' y 'CXC VENCIDAS'.")
            return

        st.info("✅ Fuente: Hojas 'CXC VIGENTES' y 'CXC VENCIDAS'")

        # Leer y normalizar cada hoja
        df_vigentes = pd.read_excel(xls, sheet_name='CXC VIGENTES')
        df_vencidas = pd.read_excel(xls, sheet_name='CXC VENCIDAS')
        
        df_vigentes = normalizar_columnas(df_vigentes)
        df_vencidas = normalizar_columnas(df_vencidas)
        
        # Renombrar columnas clave para unificación
        column_rename = {
            'razon_social': 'cliente',
            'linea_de_negocio': 'linea_negocio',
            'vendedor': 'vendedor',
            'saldo': 'saldo',
            'saldo_usd': 'saldo',  # Priorizar saldo USD si existe
            'estatus': 'estatus'
        }
        
        for df in [df_vigentes, df_vencidas]:
            for original, nuevo in column_rename.items():
                if original in df.columns:
                    df.rename(columns={original: nuevo}, inplace=True)
        
        # Agregar columna de origen
        df_vigentes['origen'] = 'VIGENTE'
        df_vencidas['origen'] = 'VENCIDA'
        
        # Unificar columnas
        common_cols = list(set(df_vigentes.columns) & set(df_vencidas.columns))
        df_cxc = pd.concat([
            df_vigentes[common_cols], 
            df_vencidas[common_cols]
        ], ignore_index=True)
        
        # Eliminar columnas completamente vacías
        df_cxc = df_cxc.dropna(axis=1, how='all')

        # Validar columna de saldo
        if 'saldo' not in df_cxc.columns:
            st.error("❌ No existe columna 'saldo' en las hojas CxC. No se puede continuar.")
            return
            
        # Convertir saldo a numérico
        df_cxc['saldo'] = pd.to_numeric(
            df_cxc['saldo'].astype(str).str.replace('[^\d.]', '', regex=True),
            errors='coerce'
        )
        
        # Manejar valores no numéricos
        if df_cxc['saldo'].isna().any():
            n_errors = df_cxc['saldo'].isna().sum()
            st.warning(f"⚠️ {n_errors} valores no numéricos en 'saldo' convertidos a 0")
            df_cxc['saldo'] = df_cxc['saldo'].fillna(0)

        # Crear estatus unificado
        if 'estatus' in df_cxc.columns:
            df_cxc['estatus'] = df_cxc['estatus'].str.upper()
        else:
            df_cxc['estatus'] = df_cxc['origen']

        st.header("📊 KPI Avanzado de Cuentas por Cobrar")

        # KPIs principales en columnas
        col1, col2, col3 = st.columns(3)
        total_cxc = df_cxc['saldo'].sum()
        col1.metric("Total CxC", f"${total_cxc:,.2f}")
        
        # Calcular montos por estatus
        vigente = df_cxc[df_cxc['estatus'].str.contains('VIGENTE')]['saldo'].sum()
        vencida = df_cxc[df_cxc['estatus'].str.contains('VENCID')]['saldo'].sum()
        
        col2.metric("CxC Vigente", f"${vigente:,.2f}", 
                   delta=f"{(vigente/total_cxc*100 if total_cxc else 0):.1f}%")
        
        col3.metric("CxC Vencida", f"${vencida:,.2f}", 
                   delta=f"{(vencida/total_cxc*100 if total_cxc else 0):.1f}%",
                   delta_color="inverse")

        # KPIs secundarios
        clientes = df_cxc['cliente'].nunique() if 'cliente' in df_cxc.columns else 0
        vendedores = df_cxc['vendedor'].nunique() if 'vendedor' in df_cxc.columns else 0
        lineas = df_cxc['linea_negocio'].nunique() if 'linea_negocio' in df_cxc.columns else 0
        
        col4, col5, col6 = st.columns(3)
        col4.metric("👥 Clientes Únicos", clientes)
        col5.metric("👤 Vendedores Únicos", vendedores)
        col6.metric("📦 Líneas de Producto", lineas)

        # Análisis de antigüedad de saldos
        st.subheader("📅 Análisis de Antigüedad")
        if 'vencimiento' in df_cxc.columns:
            try:
                df_cxc['fecha_vencimiento'] = pd.to_datetime(
                    df_cxc['vencimiento'], errors='coerce', dayfirst=True
                )
                
                hoy = pd.Timestamp.today()
                df_cxc['dias_vencido'] = (hoy - df_cxc['fecha_vencimiento']).dt.days
                
                # Clasificar por rangos
                bins = [-np.inf, 0, 30, 60, 90, 180, np.inf]
                labels = ['Por vencer', '1-30 días', '31-60 días', '61-90 días', '91-180 días', '>180 días']
                df_cxc['antigüedad'] = pd.cut(
                    df_cxc['dias_vencido'], 
                    bins=bins, 
                    labels=labels
                )
                
                # Resumen de antigüedad
                antiguedad_df = df_cxc.groupby('antigüedad')['saldo'].sum().reset_index()
                antiguedad_df['porcentaje'] = (antiguedad_df['saldo'] / total_cxc) * 100
                st.dataframe(antiguedad_df.style.format({
                    'saldo': '${:,.2f}',
                    'porcentaje': '{:.1f}%'
                }))
                
                # Gráfico de barras
                st.bar_chart(antiguedad_df.set_index('antigüedad')['saldo'])
                
            except Exception as e:
                st.error(f"❌ Error en análisis de vencimientos: {str(e)}")
        else:
            st.warning("ℹ️ No se encontró columna 'vencimiento' para análisis de antigüedad")

        # Sección de tablas dinámicas
        st.subheader("🔍 Desglose Detallado")
        
        # Selector de dimensión
        dimension = st.selectbox("Seleccionar dimensión para análisis", 
                                ["Vendedor", "Cliente", "Línea de Producto"],
                                index=0)
        
        dim_map = {
            "Vendedor": "vendedor",
            "Cliente": "cliente",
            "Línea de Producto": "linea_negocio"
        }
        
        if dim_map[dimension] in df_cxc.columns:
            pivot = df_cxc.pivot_table(
                index=dim_map[dimension],
                values='saldo',
                aggfunc=['sum', 'count']
            ).reset_index()
            
            pivot.columns = [dimension, 'Saldo Total', 'Documentos']
            pivot['Porcentaje'] = (pivot['Saldo Total'] / total_cxc) * 100
            
            st.dataframe(
                pivot.sort_values('Saldo Total', ascending=False)
                .style.format({
                    'Saldo Total': '${:,.2f}',
                    'Porcentaje': '{:.1f}%'
                })
            )
            
            # Top 10
            st.subheader(f"🔝 Top 10 {dimension} con Mayor Saldo")
            top10 = pivot.nlargest(10, 'Saldo Total')
            st.bar_chart(top10.set_index(dimension)['Saldo Total'])
        else:
            st.warning(f"⚠️ No existe columna para {dimension} en los datos")

        # Análisis de concentración
        st.subheader("📈 Análisis de Concentración")
        if 'cliente' in df_cxc.columns:
            client_pivot = df_cxc.pivot_table(
                index='cliente',
                values='saldo',
                aggfunc='sum'
            ).reset_index().sort_values('saldo', ascending=False)
            
            client_pivot['cumsum'] = client_pivot['saldo'].cumsum()
            client_pivot['cum_pct'] = (client_pivot['cumsum'] / total_cxc) * 100
            
            # Calcular Pareto (80/20)
            pareto_index = np.argmax(client_pivot['cum_pct'] >= 80)
            pareto_clients = client_pivot.iloc[:pareto_index+1]
            
            st.info(f"🔍 Principales {len(pareto_clients)} clientes concentran el 80% del saldo")
            st.dataframe(
                pareto_clients.style.format({
                    'saldo': '${:,.2f}',
                    'cum_pct': '{:.1f}%'
                })
            )
            
            # Gráfico de Pareto
            st.area_chart(pareto_clients.set_index('cliente')[['cum_pct']])

    except Exception as e:
        st.error(f"❌ Error crítico: {str(e)}")