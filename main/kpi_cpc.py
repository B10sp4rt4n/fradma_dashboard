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
        # NUEVOS KPIs ADICIONALES =========================================================
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

        # Análisis de riesgo por antigüedad
        st.subheader("📅 Perfil de Riesgo por Antigüedad")
        if 'fecha_vencimiento' in df_deudas.columns:
            try:
                df_deudas['fecha_vencimiento'] = pd.to_datetime(
                    df_deudas['fecha_vencimiento'], errors='coerce', dayfirst=True
                )
                
                hoy = pd.Timestamp.today()
                df_deudas['dias_vencido'] = (hoy - df_deudas['fecha_vencimiento']).dt.days
                
                # Clasificación de riesgo con colores
                bins = [-np.inf, 0, 30, 60, 90, 180, np.inf]
                labels = ['Por vencer', 
                         '1-30 días', 
                         '31-60 días', 
                         '61-90 días', 
                         '91-180 días', 
                         '>180 días']
                colores = ['#4CAF50', '#8BC34A', '#FFEB3B', '#FF9800', '#F44336', '#B71C1C']  # Verde, verde claro, amarillo, naranja, rojo, rojo oscuro
                
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
                
                # Mostrar semáforo visual
                st.write("### 🔴🟠🟡🟢 Semáforo de Riesgo")
                
                # Crear tarjetas de colores para cada categoría
                for idx, row in riesgo_df.iterrows():
                    nivel = row['nivel_riesgo']
                    monto = row['saldo_adeudado']
                    pct = row['porcentaje']
                    color = colores[idx]
                    
                    # Crear tarjeta con color de fondo
                    st.markdown(
                        f"""
                        <div style="background-color:{color}; padding:10px; border-radius:5px; margin-bottom:10px; color:white; font-weight:bold;">
                            <div style="display:flex; justify-content:space-between;">
                                <span>{nivel}</span>
                                <span>${monto:,.2f} ({pct:.1f}%)</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                # Gráfico de barras con colores por categoría
                st.write("### 📊 Distribución de Deuda por Antigüedad")
                fig, ax = plt.subplots()
                bars = ax.bar(riesgo_df['nivel_riesgo'], riesgo_df['saldo_adeudado'], color=colores)
                ax.set_title('Distribución por Antigüedad de Deuda')
                ax.set_ylabel('Monto Adeudado ($)')
                ax.yaxis.set_major_formatter('${x:,.0f}')
                plt.xticks(rotation=45)
                
                # Agregar etiquetas de valor
                for bar in bars:
                    height = bar.get_height()
                    ax.annotate(f'${height:,.0f}',
                                xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 3),  # 3 points vertical offset
                                textcoords="offset points",
                                ha='center', va='bottom')
                
                st.pyplot(fig)
                
            except Exception as e:
                st.error(f"❌ Error en análisis de vencimientos: {str(e)}")
        else:
            st.warning("ℹ️ No se encontró columna de vencimiento")
            
        # =====================================================================
        # ANÁLISIS DE AGENTES (VENDEDORES) CON LÓGICA DE ANTIGÜEDAD
        # =====================================================================
        st.subheader("👤 Distribución de Deuda por Agente")
        
        if 'vendedor' in df_deudas.columns:
            # Asegurar que tenemos los días vencidos calculados
            if 'dias_vencido' not in df_deudas.columns and 'fecha_vencimiento' in df_deudas.columns:
                try:
                    hoy = pd.Timestamp.today()
                    df_deudas['dias_vencido'] = (hoy - pd.to_datetime(df_deudas['fecha_vencimiento'], errors='coerce')).dt.days
                except:
                    pass
            
            if 'dias_vencido' in df_deudas.columns:
                # Definir categorías y colores para agentes
                bins_agentes = [-np.inf, 0, 30, 60, 90, np.inf]
                labels_agentes = ['Por vencer', '1-30 días', '31-60 días', '61-90 días', '>90 días']
                colores_agentes = ['#4CAF50', '#8BC34A', '#FFEB3B', '#FF9800', '#F44336']  # Verde, verde claro, amarillo, naranja, rojo
                
                # Clasificar la deuda de los agentes
                df_deudas['categoria_agente'] = pd.cut(
                    df_deudas['dias_vencido'], 
                    bins=bins_agentes, 
                    labels=labels_agentes
                )
                
                # Agrupar por agente y categoría
                agente_categoria = df_deudas.groupby(['vendedor', 'categoria_agente'])['saldo_adeudado'].sum().unstack().fillna(0)
                
                # Ordenar por el total de deuda
                agente_categoria['Total'] = agente_categoria.sum(axis=1)
                agente_categoria = agente_categoria.sort_values('Total', ascending=False)
                
                # Crear gráfico de barras apiladas
                st.write("### 📊 Distribución por Agente y Antigüedad")
                fig, ax = plt.subplots(figsize=(12, 6))
                
                # Preparar datos para el gráfico
                bottom = np.zeros(len(agente_categoria))
                for i, categoria in enumerate(labels_agentes):
                    if categoria in agente_categoria.columns:
                        valores = agente_categoria[categoria]
                        ax.bar(agente_categoria.index, valores, bottom=bottom, label=categoria, color=colores_agentes[i])
                        bottom += valores
                
                # Personalizar gráfico
                ax.set_title('Deuda por Agente y Antigüedad', fontsize=14)
                ax.set_ylabel('Monto Adeudado ($)', fontsize=12)
                ax.set_xlabel('Agente', fontsize=12)
                ax.tick_params(axis='x', rotation=45)
                ax.legend(title='Días Vencidos', loc='upper right')
                ax.yaxis.set_major_formatter('${x:,.0f}')
                
                st.pyplot(fig)
                
                # Mostrar tabla resumen
                st.write("### 📋 Resumen por Agente")
                resumen_agente = agente_categoria.copy()
                resumen_agente = resumen_agente.sort_values('Total', ascending=False)
                
                # Formatear valores
                for col in resumen_agente.columns:
                    if col != 'Total':
                        resumen_agente[col] = resumen_agente[col].apply(lambda x: f"${x:,.2f}" if x > 0 else "")
                resumen_agente['Total'] = resumen_agente['Total'].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(resumen_agente)
                
            else:
                st.warning("ℹ️ No se pudo calcular la antigüedad para los agentes")
        else:
            st.warning("ℹ️ No se encontró información de agentes (vendedores)")

        # Desglose detallado por deudor (CLIENTE - COLUMNA F)
        st.subheader("🔍 Detalle Completo por Deudor (Columna Cliente)")
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

        # Resumen ejecutivo
        st.subheader("📝 Resumen Ejecutivo")
        st.write(f"Fradma tiene **${total_adeudado:,.2f}** en deudas pendientes de cobro")
        st.write(f"El principal deudor es **{top_deudores.index[0]}** con **${top_deudores.iloc[0]:,.2f}**")
        
        if 'dias_vencido' in df_deudas.columns:
            deuda_vencida = df_deudas[df_deudas['dias_vencido'] > 0]['saldo_adeudado'].sum()
            st.write(f"- **${deuda_vencida:,.2f} en deuda vencida**")
        
        st.write("Este reporte se basa en la columna 'Cliente' (F) para identificar deudores.")

    except Exception as e:
        st.error(f"❌ Error crítico: {str(e)}")
        import traceback
        st.error(traceback.format_exc())