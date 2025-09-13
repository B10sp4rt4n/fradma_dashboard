import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path
from etl_ventas_items import load_hoja3_to_df, insert_ventas_items, DB_PATH

def _leer_hashes_existentes(db_path: str):
    Path(db_path).touch(exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS ventas_items (
          id INTEGER PRIMARY KEY,
          fecha TEXT, anio INTEGER, mes INTEGER,
          factura TEXT, orden_compra TEXT, cliente TEXT,
          marca TEXT, sublinea TEXT, clave_producto TEXT,
          cantidad REAL, unidad TEXT,
          importe_usd REAL NOT NULL,
          moneda_origen TEXT, tc REAL,
          hash_row TEXT NOT NULL,
          created_at TEXT DEFAULT (datetime('now')),
          UNIQUE(hash_row)
        )
        """)
        cur = con.cursor()
        cur.execute("SELECT hash_row FROM ventas_items")
        rows = cur.fetchall()
    return set(r[0] for r in rows)

def run():
    st.subheader("🧩 Consolidar ventas (Selector de Hoja)")
    st.caption("Sube un Excel y elige la hoja a procesar. Por defecto: índice 2 (Hoja 3).")

    archivo = st.file_uploader("Reporte de ventas (.xlsx)", type=["xlsx"])
    db_path = st.text_input("Ruta DB SQLite", value=DB_PATH)

    if "etl_preview_df" not in st.session_state:
        st.session_state.etl_preview_df = None
        st.session_state.etl_resumen = None

    if archivo is not None:
        try:
            xls = pd.ExcelFile(archivo)
            hojas = xls.sheet_names
            hoja_seleccionada = st.selectbox(
                "📄 Selecciona la hoja a procesar",
                options=list(range(len(hojas))),
                format_func=lambda idx: f"{idx} - {hojas[idx]}",
                index=2 if len(hojas) > 2 else 0
            )
        except Exception as e:
            st.error(f"❌ Error leyendo hojas del archivo: {e}")
            return

        analizar = st.button("🔍 Analizar hoja seleccionada", type="primary")

        if analizar:
            try:
                df_full = load_hoja3_to_df(archivo, hoja_seleccionada)
                hashes_existentes = _leer_hashes_existentes(db_path)
                df_nuevos = df_full[~df_full["hash_row"].isin(hashes_existentes)].copy()

                total = len(df_full)
                nuevos = len(df_nuevos)
                duplicados = total - nuevos

                # ✅ evitar nombres duplicados en el preview
                df_nuevos = df_nuevos.loc[:, ~df_nuevos.columns.duplicated(keep="first")]

                st.session_state.etl_preview_df = df_nuevos
                st.session_state.etl_resumen = {
                    "total_leidos": total,
                    "nuevos": nuevos,
                    "duplicados": duplicados
                }

                st.success(f"Leídas {total} filas. Nuevas: {nuevos}. Repetidas (hash): {duplicados}.")
                if nuevos > 0:
                    st.dataframe(df_nuevos.head(50))
                else:
                    st.info("No hay filas nuevas para insertar.")
            except Exception as e:
                st.error(f"❌ Error analizando la hoja: {e}")

    if st.session_state.etl_preview_df is not None and len(st.session_state.etl_preview_df) > 0:
        insertar = st.button(f"⬇️ Insertar {len(st.session_state.etl_preview_df)} filas nuevas en SQLite")
        if insertar:
            try:
                ins, ign = insert_ventas_items(st.session_state.etl_preview_df, db_path=db_path)
                st.success(f"✅ Insertados: {ins} | Ignorados por duplicado: {ign}")
                st.session_state.etl_preview_df = None
                st.session_state.etl_resumen = None
            except Exception as e:
                st.error(f"❌ Error insertando en SQLite: {e}")

    if st.session_state.etl_resumen:
        st.caption(f"Resumen: {st.session_state.etl_resumen}")

# Permite correr este UI de forma independiente:
# streamlit run main/etl_ventas_items_ui.py
if __name__ == "__main__":
    run()
