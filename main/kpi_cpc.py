import streamlit as st
import pandas as pd
import numpy as np
from unidecode import unidecode
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os # Importamos os para manejar rutas de archivo

def normalizar_columnas(df):
    """
    Normaliza los nombres de las columnas de un DataFrame, eliminando tildes,
    espacios y convirtiéndolos a minúsculas, y maneja duplicados.
    """
    nuevas_columnas = []
    contador = {}
    for col in df.columns:
        col_str = str(col).lower().strip().replace(" ", "_")
        col_str = unidecode(col_str) # Elimina tildes y caracteres especiales
        
        # Manejar columnas duplicadas
        if col_str in contador:
            contador[col_str] += 1
            col_str = f"{col_str}_{contador[col_str]}"
        else:
            contador[col_str] = 1
            
        nuevas_columnas.append(col_str)
    df.columns = nuevas_columnas
    return df

def run_local_files(): # La función ya no necesita argumentos de archivo
    """
    Función principal para procesar archivos Excel locales y generar el dashboard.
    """
    # Definimos las rutas de los archivos locales
    # ASUMIMOS que los archivos están en la misma carpeta que este script.
    # Si están en otra ubicación, DEBES CAMBIAR estas rutas.
    file_vigentes = "CXC VIGENTES.xlsx"
    file_vencidas = "CXC VENCIDAS.xlsx"

    # Verificar si los archivos existen antes de intentar leerlos
    if not os.path.exists(file_vigentes) or not os.path.exists(file_vencidas):
        st.error(f"❌ Error: No se encontraron los archivos '{file_vigentes}' y/o '{file_vencidas}' en la ubicación esperada. Asegúrate de que estén en la misma carpeta que este script.")
        st.stop() # Detener la ejecución si los archivos no existen

    try:
        st.info(f"✅ Fuente: Procesando archivos locales '{file_vigentes}' y '{file_vencidas}'.")

        # Leer los DataFrames directamente desde las rutas locales
        df_vigentes = pd.read_excel(file_vigentes)
        df_vencidas = pd.read_excel(file_vencidas)

        # Normalizar columnas de ambos DataFrames
        df_vigentes = normalizar_columnas(df_vigentes)
        df_vencidas = normalizar_columnas(df_vencidas)

        # Unificar DataFrames
        df_deudas = pd.concat([df_vigentes, df_vencidas], ignore_index=True)

        # Convertir tipos de datos
        df_deudas['fecha_vencimiento'] = pd.to_datetime(df_deudas['fecha_vencimiento'], errors='coerce')
        df_deudas['saldo_adeudado'] = pd.to_numeric(df_deudas['saldo_adeudado'], errors='coerce')
        
        # Eliminar filas con NaN en columnas críticas
        df_deudas.dropna(subset=['fecha_vencimiento', 'saldo_adeudado'], inplace=True)

        # Calcular días vencidos
        df_deudas['dias_vencido'] = (datetime.now() - df_deudas['fecha_vencimiento']).dt.days
        
        # Calcular el total adeudado
        total_adeudado = df_deudas['saldo_adeudado'].sum()

        st.title("💰 Reporte de Cuentas por Cobrar (Fradma)")
        st.markdown(f"### Saldo Total Adeudado: **${total_adeudado:,.2f}**")

        # --- Análisis de Deudas por Antigüedad (EXISTENTE) ---
        st.subheader("📊 Análisis de Deudas por Antigüedad")
        
        # Define rangos de antigüedad
        rangos_antiguedad = {
            "Vigente": lambda x: x <= 0,
            "1-30 días vencido": lambda x: x > 0 and x <= 30,
            "31-60 días vencido": lambda x: x > 30 and x <= 60,
            "61-90 días vencido": lambda x: x > 60 and x <= 90,
            "Más de 90 días vencido": lambda x: x > 90
        }
        
        data_antiguedad = {}
        for rango, condicion in rangos_antiguedad.items():
            saldo = df_deudas[condicion(df_deudas['dias_vencido'])]['saldo_adeudado'].sum()
            data_antiguedad[rango] = saldo

        df_antiguedad = pd.DataFrame(list(data_antiguedad.items()), columns=['Rango', 'Saldo Adeudado'])
        df_antiguedad['Porcentaje'] = (df_antiguedad['Saldo Adeudado'] / total_adeudado * 100).round(2)
        
        st.dataframe(df_antiguedad.style.format({
            'Saldo Adeudado': "${:,.2f}",
            'Porcentaje': "{:.2f}%"
        }))

        # Gráfico de pastel por antigüedad
        if total_adeudado > 0:
            fig_pie, ax_pie = plt.subplots(figsize=(8, 8))
            
            # Colores personalizados (ej. azul para vigente, rojos para vencidos)
            colores = [
                '#66c2a5' if r == 'Vigente' else
                '#fc8d62' if r == '1-30 días vencido' else
                '#e78ac3' if r == '31-60 días vencido' else
                '#a6d854' if r == '61-90 días vencido' else
                '#e5c494'
                for r in df_antiguedad['Rango']
            ]

            wedges, texts, autotexts = ax_pie.pie(
                df_antiguedad['Saldo Adeudado'], 
                labels=df_antiguedad['Rango'], 
                autopct='%1.1f%%', 
                startangle=90,
                colors=colores,
                pctdistance=0.85 # Distancia de los porcentajes del centro
            )
            ax_pie.axis('equal') # Equal aspect ratio ensures that pie is drawn as a circle.
            ax_pie.set_title('Distribución de Deuda por Antigüedad')
            st.pyplot(fig_pie)
        else:
            st.info("ℹ️ No hay deuda para generar gráfico de antigüedad.")

        # --- Detalle de Deudores Principales (EXISTENTE) ---
        st.subheader("🔍 Detalle de Deudores Principales")
        
        if 'deudor' in df_deudas.columns:
            deudores_principales = df_deudas.groupby('deudor')['saldo_adeudado'].sum().sort_values(ascending=False)
            
            if not deudores_principales.empty:
                st.write("Top 10 Deudores:")
                st.dataframe(deudores_principales.head(10).reset_index().style.format({
                    'saldo_adeudado': "${:,.2f}"
                }))
                
                # Permite al usuario seleccionar un deudor para ver el detalle
                st.write("---")
                st.subheader("🔎 Búsqueda de Deudor Individual")
                deudor_seleccionado = st.selectbox(
                    "Selecciona un deudor para ver el detalle:",
                    [''] + list(deudores_principales.index.unique())
                )
                
                if deudor_seleccionado:
                    deudor_df = df_deudas[df_deudas['deudor'] == deudor_seleccionado].copy()
                    
                    st.write(f"### Detalle para: {deudor_seleccionado}")
                    
                    total_deudor = deudor_df['saldo_adeudado'].sum()
                    st.write(f"**Saldo Total Adeudado por {deudor_seleccionado}: ${total_deudor:,.2f}**")
                    
                    # Columnas a mostrar para el detalle del deudor
                    cols = [col for col in ['folio', 'fecha_vencimiento', 'saldo_adeudado', 'dias_vencido'] if col in deudor_df.columns]
                    st.dataframe(deudor_df[cols].sort_values('fecha_vencimiento', ascending=False).style.format({
                        'saldo_adeudado': "${:,.2f}"
                    }))
                    
                    # Histórico de pagos (si existe la columna y hay lógica)
                    if 'fecha_pago' in df_deudas.columns and 'monto_pagado' in df_deudas.columns:
                        st.write("**Histórico de pagos:**")
                        pagos = deudor_df[deudor_df['monto_pagado'] > 0] 
                        if not pagos.empty:
                            st.dataframe(pagos[['fecha_pago', 'monto_pagado']].style.format({'monto_pagado': "${:,.2f}"}))
                        else:
                            st.info("ℹ️ No se encontraron registros de pagos recientes para este deudor.")
                    else:
                        st.info("ℹ️ Columnas 'fecha_pago' o 'monto_pagado' no encontradas para el histórico de pagos.")
            else:
                st.warning("ℹ️ No se encontró información de deudores principales.")
        else:
            st.warning("⚠️ La columna 'deudor' no se encontró para el análisis de deudores principales.")

        # --- NUEVA SECCIÓN: Gráficos de Deuda por Agente (AÑADIDA) ---
        st.subheader("📈 Deuda Pendiente por Agente")
        
        if 'agente' in df_deudas.columns:
            deuda_por_agente = df_deudas.groupby('agente')['saldo_adeudado'].sum().sort_values(ascending=False)
            
            if not deuda_por_agente.empty:
                fig_agente, ax_agente = plt.subplots(figsize=(12, 7))
                deuda_por_agente.plot(kind='bar', ax=ax_agente, color='teal')
                ax_agente.set_title('Deuda Total Pendiente por Agente')
                ax_agente.set_xlabel('Agente')
                ax_agente.set_ylabel('Saldo Adeudado')
                ax_agente.ticklabel_format(style='plain', axis='y') 
                plt.xticks(rotation=45, ha='right') 
                plt.tight_layout() 
                st.pyplot(fig_agente)

                st.write("Detalle de Deuda por Agente:")
                st.dataframe(deuda_por_agente.reset_index().style.format({
                    'saldo_adeudado': "${:,.2f}"
                }))
            else:
                st.info("ℹ️ No hay datos disponibles para generar el gráfico de deuda por agente (después de filtros o en caso de datos vacíos).")
        else:
            st.warning("⚠️ No se encontró la columna 'agente' en los datos para realizar el análisis por agente. Asegúrate de que existe en tus archivos Excel.")


        # --- Resumen Ejecutivo (EXISTENTE) ---
        st.subheader("📝 Resumen Ejecutivo")
        
        st.write(f"Fradma tiene **${total_adeudado:,.2f}** en deudas pendientes de cobro, distribuidos en:")
        
        if 'deudor' in df_deudas.columns:
            num_deudores = df_deudas['deudor'].nunique()
            st.write(f"- **{num_deudores} deudores diferentes**")
        
        if 'dias_vencido' in df_deudas.columns:
            deuda_vencida = df_deudas[df_deudas['dias_vencido'] > 0]['saldo_adeudado'].sum()
            st.write(f"- **${deuda_vencida:,.2f}** corresponde a **deuda vencida**.")
            
            porcentaje_vencido = (deuda_vencida / total_adeudado * 100).round(2) if total_adeudado > 0 else 0
            st.write(f"- Lo que representa un **{porcentaje_vencido}%** del total adeudado.")
        
        st.write("---")
        st.write("Este informe proporciona una visión general de las cuentas por cobrar, ayudando a identificar áreas de enfoque para la gestión de la cartera.")

    except Exception as e:
        st.error(f"Se produjo un error al procesar los archivos: {e}")
        st.info("Asegúrate de que los archivos Excel no estén abiertos y que las hojas 'CXC VIGENTES' y 'CXC VENCIDAS' existan y contengan datos válidos.")


# Ejecutar la aplicación sin el uploader
# NOTA IMPORTANTE: Los archivos 'CXC VIGENTES.xlsx' y 'CXC VENCIDAS.xlsx'
# DEBEN ESTAR EN LA MISMA CARPETA QUE ESTE SCRIPT kpi_cpc.py
st.sidebar.title("Configuración de Reporte")
st.sidebar.info("Este reporte procesa automáticamente los archivos 'CXC VIGENTES.xlsx' y 'CXC VENCIDAS.xlsx' ubicados en la misma carpeta del script.")

run_local_files()