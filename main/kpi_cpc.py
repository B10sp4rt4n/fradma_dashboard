import streamlit as st
import pandas as pd

def run(archivo):
    if not archivo.name.endswith(('.xls', '.xlsx')):
        st.error("❌ Solo se aceptan archivos Excel para el KPI CxC.")
        return

    xls = pd.ExcelFile(archivo)
    hojas = xls.sheet_names

    if "CXC VIGENTES" not in hojas or "CXC VENCIDAS" not in hojas:
        st.error("❌ No se encontraron ambas hojas necesarias: 'CXC VIGENTES' y 'CXC VENCIDAS'.")
        return

    st.info("Fuente: Hojas 'CXC VIGENTES' y 'CXC VENCIDAS'")

    df_cxc_vigentes = pd.read_excel(xls, sheet_name='CXC VIGENTES')
    df_cxc_vencidas = pd.read_excel(xls, sheet_name='CXC VENCIDAS')
    df_cxc = pd.concat([df_cxc_vigentes, df_cxc_vencidas], ignore_index=True)
    df_cxc.columns = df_cxc.columns.str.lower().str.strip()
    df_cxc = df_cxc.dropna(axis=1, how='all')

    if 'saldo' not in df_cxc.columns:
        st.error("❌ No existe columna 'saldo' en las hojas CxC. No se puede continuar.")
        return

    st.header("📌 KPI General de CxC")

    total_cxc = df_cxc['saldo'].sum()
    total_clientes = df_cxc['cliente'].nunique() if 'cliente' in df_cxc.columns else 0
    total_vendedores = df_cxc['vendedor'].nunique() if 'vendedor' in df_cxc.columns else 0
    total_lineas = df_cxc['linea de negocio'].nunique() if 'linea de negocio' in df_cxc.columns else 0

    st.metric("Total CxC", f"${total_cxc:,.2f}")
    st.metric("Clientes únicos", total_clientes)
    st.metric("Vendedores únicos", total_vendedores)
    st.metric("Líneas de producto únicas", total_lineas)

    # Pivot por vendedor
    if 'vendedor' in df_cxc.columns:
        st.subheader("📋 Cobranza por Vendedor")
        pivot_vendedor = df_cxc.pivot_table(index='vendedor', values='saldo', aggfunc='sum').reset_index()
        pivot_vendedor["saldo"] = pivot_vendedor["saldo"].map("${:,.2f}".format)
        st.dataframe(pivot_vendedor)

    # Pivot por cliente
    if 'cliente' in df_cxc.columns:
        st.subheader("📋 Cobranza por Cliente")
        pivot_cliente = df_cxc.pivot_table(index='cliente', values='saldo', aggfunc='sum').reset_index()
        pivot_cliente["saldo"] = pivot_cliente["saldo"].map("${:,.2f}".format)
        st.dataframe(pivot_cliente)

    # Pivot por línea de negocio
    if 'linea de negocio' in df_cxc.columns:
        st.subheader("📋 Cobranza por Línea de Producto")
        pivot_linea = df_cxc.pivot_table(index='linea de negocio', values='saldo', aggfunc='sum').reset_index()
        pivot_linea["saldo"] = pivot_linea["saldo"].map("${:,.2f}".format)
        st.dataframe(pivot_linea)
