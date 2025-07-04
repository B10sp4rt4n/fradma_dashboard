import streamlit as st
import pandas as pd
import numpy as np
from unidecode import unidecode
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def normalizar_columnas(df):
    nuevas_columnas = []
    contador = {}
    for col in df.columns:
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str)
        
        if col_str in contador:
            contador[col_str] += 1
            col_str = f"{col_str}_{contador[col_str]}"
        else:
            contador[col_str] = 1
            
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df

def run(archivo):
    if not archivo.name.endswith(('.xls', '.xlsx')):
        st.error("❌ Solo se aceptan archivos Excel para el reporte de deudas.")
        return

    try:
        xls = pd.ExcelFile(archivo)
        hojas = xls.sheet_names
        
        if "CXC VIGENTES" not in hojas or "CXC VENCIDAS" not in hojas:
            st.error("❌ No se encontraron las hojas requeridas: 'CXC VIGENTES' y 'CXC VENCIDAS'.")
            return

        st.info("✅ Fuente: Hojas 'CXC VIGENTES' y 'CXC VENCIDAS'")

        # Leer y normalizar datos
        df_vigentes = pd.read_excel(xls, sheet_name='CXC VIGENTES')
        df_vencidas = pd.read_excel(xls, sheet_name='CXC VENCIDAS')
        
        df_vigentes = normalizar_columnas(df_vigentes)
        df_vencidas = normalizar_columnas(df_vencidas)
        
        # Renombrar columnas clave - PRIORIZAR COLUMNA F (CLIENTE)
        for df in [df_vigentes, df_vencidas]:
            # 1. Priorizar columna 'cliente' (columna F)
            if 'cliente' in df.columns:
                df.rename(columns={'cliente': 'deudor'}, inplace=True)
                
                # Si también existe 'razon_social', eliminarla
                if 'razon_social' in df.columns:
                    df.drop(columns=['razon_social'], inplace=True)
                    
            # 2. Si no existe 'cliente', usar 'razon_social' como respaldo
            elif 'razon_social' in df.columns:
                df.rename(columns={'razon_social': 'deudor'}, inplace=True)
            
            # Renombrar otras columnas importantes
            column_rename = {
                'linea_de_negocio': 'linea_negocio',
                'vendedor': 'vendedor',
                'saldo': 'saldo_adeudado',
                'saldo_usd': 'saldo_adeudado',
                'estatus': 'estatus',
                'vencimiento': 'fecha_vencimiento'
            }
            
            for original, nuevo in column_rename.items():
                if original in df.columns and nuevo not in df.columns:
                    df.rename(columns={original: nuevo}, inplace=True)
        
        # Agregar origen
        df_vigentes['origen'] = 'VIGENTE'
        df_vencidas['origen'] = 'VENCIDA'
        
        # Unificar columnas
        common_cols = list(set(df_vigentes.columns) & set(df_vencidas.columns))
        df_deudas = pd.concat([
            df_vigentes[common_cols], 
            df_vencidas[common_cols]
        ], ignore_index=True)
        
        # Limpieza
        df_deudas = df_deudas.dropna(axis=1, how='all')
        
        # Manejar duplicados
        duplicados = df_deudas.columns[df_deudas.columns.duplicated()]
        if not duplicados.empty:
            df_deudas = df_deudas.loc[:, ~df_deudas.columns.duplicated(keep='first')]

        # Validar columna clave
        if 'saldo_adeudado' not in df_deudas.columns:
            st.error("❌ No existe columna de saldo en los datos.")
            st.write("Columnas disponibles:", df_deudas.columns.tolist())
            return
            
        # Validar columna de deudor
        if 'deudor' not in df_deudas.columns:
            st.error("❌ No se encontró columna para identificar deudores.")
            st.write("Se esperaba 'cliente' o 'razon_social' en los encabezados")
            return
            
        # Convertir saldo
        saldo_serie = df_deudas['saldo_adeudado'].astype(str)
        saldo_limpio = saldo_serie.str.replace(r'[^\d.]', '', regex=True)
        df_deudas['saldo_adeudado'] = pd.to_numeric(saldo_limpio, errors='coerce').fillna(0)

        # ---------------------------------------------------------------------
        # REPORTE DE DEUDAS A FRADMA (USANDO COLUMNA CORRECTA)
        # ---------------------------------------------------------------------
        st.header("📊 Reporte de Deudas a Fradma")
        
        # KPIs principales
        except Exception as e:
            st.error(f"⚠️ Error inesperado: {str(e)}")
# [REMOVIDO POR REUBICACIÓN] =========================================================
        # 1. KPI: Tasa de concentración Top 3
        top_3 = top_deudores.head(3).sum()
        concentracion_3 = (top_3 / total_adeudado) * 100
        st.metric("Concentración Top 3 Deudores", f"{concentracion_3:.1f}%", help="Porcentaje de deuda total concentrada en los 3 principales deudores")

        # 2. KPI: Alerta de deuda vencida crítica > 180 días
        if 'dias_vencido' in df_deudas.columns:
            deuda_critica = df_deudas[df_deudas['dias_vencido'] > 180]['saldo_adeudado'].sum()
            if deuda_critica > 0:
                st.warning(f"⚠️ Deuda crítica (vencida > 180 días): ${deuda_critica:,.2f}")

        # 3. KPI: Tasa de vencimiento por agente
        if 'vendedor' in df_deudas.columns and 'dias_vencido' in df_deudas.columns:
            df_agente_riesgo = df_deudas.copy()
            df_agente_riesgo['vencido'] = df_agente_riesgo['dias_vencido'] > 0
            resumen_riesgo = df_agente_riesgo.groupby('vendedor').agg(
                total_adeudado=('saldo_adeudado', 'sum'),
                vencido=('vencido', 'sum')
            )
            resumen_riesgo['tasa_riesgo'] = (resumen_riesgo['vencido'] / resumen_riesgo['total_adeudado']) * 100
            resumen_riesgo = resumen_riesgo.sort_values('tasa_riesgo', ascending=False)
            st.subheader("📈 Tasa de Deuda Vencida por Agente")
            st.dataframe(resumen_riesgo.style.format({
                'total_adeudado': '${:,.2f}',
                'tasa_riesgo': '{:.1f}%'
            }))

        total_adeudado = df_deudas['saldo_adeudado'].sum()
        col1, col2 = st.columns(2)
        col1.metric("Total Adeudado a Fradma", f"${total_adeudado:,.2f}")
        
        # Calcular vencimientos
        try:
            mask_vencida = df_deudas['estatus'].str.contains('VENCID', na=False)
            vencida = df_deudas[mask_vencida]['saldo_adeudado'].sum()
            col2.metric("Deuda Vencida", f"${vencida:,.2f}", 
                       delta=f"{(vencida/total_adeudado*100):.1f}%",
                       delta_color="inverse")
        except:
            vencida = 0

        # Top 5 deudores (USANDO COLUMNA F - CLIENTE)
        st.subheader("🔝 Principales Deudores (Columna Cliente)")
        top_deudores = df_deudas.groupby('deudor')['saldo_adeudado'].sum().nlargest(5)
        st.dataframe(top_deudores.reset_index().rename(
            columns={'deudor': 'Cliente (Col F)', 'saldo_adeudado': 'Monto Adeudado ($)'}
        ).style.format({'Monto Adeudado ($)': '${:,.2f}'}))
        
        # Gráfico de concentración
        st.bar_chart(top_deudores)

        # NUEVOS KPIs ADICIONALES =========================================================
        if not top_deudores.empty:
            # 1. KPI: Tasa de concentración Top 3
            top_3 = top_deudores.head(3).sum()
            concentracion_3 = (top_3 / total_adeudado) * 100
            st.metric("Concentración Top 3 Deudores", f"{concentracion_3:.1f}%", help="Porcentaje de deuda total concentrada en los 3 principales deudores")

        # 2. KPI: Alerta de deuda vencida crítica > 180 días
        if 'dias_vencido' in df_deudas.columns:
            deuda_critica = df_deudas[df_deudas['dias_vencido'] > 180]['saldo_adeudado'].sum()
            if deuda_critica > 0:
                st.warning(f"⚠️ Deuda crítica (vencida > 180 días): ${deuda_critica:,.2f}")

        # 3. KPI: Tasa de vencimiento por agente
        if 'vendedor' in df_deudas.columns and 'dias_vencido' in df_deudas.columns:
            df_agente_riesgo = df_deudas.copy()
            df_agente_riesgo['vencido'] = df_agente_riesgo['dias_vencido'] > 0
            resumen_riesgo = df_agente_riesgo.groupby('vendedor').agg(
                total_adeudado=('saldo_adeudado', 'sum'),
                vencido=('vencido', 'sum')
            )
            resumen_riesgo['tasa_riesgo'] = (resumen_riesgo['vencido'] / resumen_riesgo['total_adeudado']) * 100
            resumen_riesgo = resumen_riesgo.sort_values('tasa_riesgo', ascending=False)
            st.subheader("📈 Tasa de Deuda Vencida por Agente")
            st.dataframe(resumen_riesgo.style.format({
                'total_adeudado': '${:,.2f}',
                'tasa_riesgo': '{:.1f}%'
            }))
