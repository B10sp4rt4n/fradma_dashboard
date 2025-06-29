import streamlit as st
import pandas as pd
import numpy as np
from unidecode import unidecode
from datetime import datetime

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
        
        # Renombrar columnas clave
        column_rename = {
            'razon_social': 'deudor',
            'linea_de_negocio': 'linea_negocio',
            'vendedor': 'vendedor',
            'saldo': 'saldo_adeudado',
            'saldo_usd': 'saldo_adeudado',
            'estatus': 'estatus'
        }
        
        for df in [df_vigentes, df_vencidas]:
            for original, nuevo in column_rename.items():
                if original in df.columns:
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
            return
            
        # Convertir saldo
        saldo_serie = df_deudas['saldo_adeudado'].astype(str)
        saldo_limpio = saldo_serie.str.replace(r'[^\d.]', '', regex=True)
        df_deudas['saldo_adeudado'] = pd.to_numeric(saldo_limpio, errors='coerce').fillna(0)

        # ---------------------------------------------------------------------
        # NUEVO ENFOQUE: REPORTE DE DEUDAS A FRADMA
        # ---------------------------------------------------------------------
        st.header("📊 Reporte de Deudas a Fradma")
        
        # KPIs principales
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

        # Top 5 deudores
        st.subheader("🔝 Principales Deudores")
        if 'deudor' in df_deudas.columns:
            top_deudores = df_deudas.groupby('deudor')['saldo_adeudado'].sum().nlargest(5)
            st.dataframe(top_deudores.reset_index().rename(
                columns={'deudor': 'Deudor', 'saldo_adeudado': 'Monto Adeudado ($)'}
            ).style.format({'Monto Adeudado ($)': '${:,.2f}'}))
            
            # Gráfico de concentración
            st.bar_chart(top_deudores)
        else:
            st.warning("ℹ️ No se encontró información de deudores")

        # Análisis de riesgo por antigüedad
        st.subheader("📅 Perfil de Riesgo por Antigüedad")
        if 'vencimiento' in df_deudas.columns:
            try:
                df_deudas['fecha_vencimiento'] = pd.to_datetime(
                    df_deudas['vencimiento'], errors='coerce', dayfirst=True
                )
                
                hoy = pd.Timestamp.today()
                df_deudas['dias_vencido'] = (hoy - df_deudas['fecha_vencimiento']).dt.days
                
                # Clasificación de riesgo
                bins = [-np.inf, 0, 30, 60, 90, 180, np.inf]
                labels = ['0. Bajo (Por vencer)', 
                         '1. Moderado (1-30 días)', 
                         '2. Medio (31-60 días)', 
                         '3. Alto (61-90 días)', 
                         '4. Crítico (91-180 días)', 
                         '5. Irrecuperable (>180 días)']
                
                df_deudas['nivel_riesgo'] = pd.cut(
                    df_deudas['dias_vencido'], 
                    bins=bins, 
                    labels=labels
                )
                
                # Resumen de riesgo
                riesgo_df = df_deudas.groupby('nivel_riesgo')['saldo_adeudado'].sum().reset_index()
                riesgo_df['porcentaje'] = (riesgo_df['saldo_adeudado'] / total_adeudado) * 100
                
                # Ordenar por nivel de riesgo
                riesgo_df = riesgo_df.sort_values('nivel_riesgo')
                
                st.dataframe(riesgo_df.style.format({
                    'saldo_adeudado': '${:,.2f}',
                    'porcentaje': '{:.1f}%'
                }))
                
                # Gráfico de riesgo
                st.bar_chart(riesgo_df.set_index('nivel_riesgo')['saldo_adeudado'])
                
            except Exception as e:
                st.error(f"❌ Error en análisis de vencimientos: {str(e)}")
        else:
            st.warning("ℹ️ No se encontró columna de vencimiento")

        # Desglose detallado por deudor
        st.subheader("🔍 Detalle Completo por Deudor")
        if 'deudor' in df_deudas.columns:
            # Seleccionar deudor
            deudores = df_deudas['deudor'].unique().tolist()
            selected_deudor = st.selectbox("Seleccionar Deudor", deudores)
            
            # Filtrar datos
            deudor_df = df_deudas[df_deudas['deudor'] == selected_deudor]
            total_deudor = deudor_df['saldo_adeudado'].sum()
            
            st.metric(f"Total Adeudado por {selected_deudor}", f"${total_deudor:,.2f}")
            
            # Mostrar documentos pendientes
            st.write("**Documentos pendientes:**")
            cols = ['fecha_vencimiento', 'saldo_adeudado', 'estatus', 'dias_vencido'] 
            cols = [c for c in cols if c in deudor_df.columns]
            st.dataframe(deudor_df[cols].sort_values('fecha_vencimiento', ascending=False))
            
            # Histórico de pagos (si existe)
            if 'fecha_pago' in df_deudas.columns:
                st.write("**Histórico de pagos:**")
                pagos = deudor_df[deudor_df['saldo_adeudado'] <= 0]  # Suponiendo que pagos son negativos
                if not pagos.empty:
                    st.dataframe(pagos[['fecha_pago', 'monto_pagado']])
                else:
                    st.info("ℹ️ No se encontraron registros de pagos recientes")
        else:
            st.warning("ℹ️ No se encontró información de deudores")

        # Resumen ejecutivo
        st.subheader("📝 Resumen Ejecutivo")
        st.write(f"Fradma tiene **${total_adeudado:,.2f}** en deudas pendientes de cobro, distribuidos en:")
        
        if 'deudor' in df_deudas.columns:
            num_deudores = df_deudas['deudor'].nunique()
            st.write(f"- **{num_deudores} deudores diferentes**")
        
        if 'dias_vencido' in df_deudas.columns:
            deuda_vencida = df_deudas[df_deudas['dias_vencido'] > 0]['saldo_adeudado'].sum()
            st.write(f"- **${deuda_vencida:,.2f} en deuda vencida**")
        
        st.write("Este reporte muestra la exposición financiera actual de Fradma con sus deudores.")

    except Exception as e:
        st.error(f"❌ Error crítico: {str(e)}")
        import traceback
        st.error(traceback.format_exc())