import sqlite3, pandas as pd, hashlib

DB_PATH = "hist.sqlite"

def _norm(s: str) -> str:
    s = str(s).lower().strip().replace("\n"," ").replace("\r"," ")
    tr = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","ü":"u"}
    for k,v in tr.items(): s = s.replace(k,v)
    return "_".join(s.split())

ALIASES = {
    "factura": ["factura","n_factur","no_factura","n°_factur","n_factur"],
    "orden_compra": ["orden_de_compra","orden_compra","oc","po","orden"],
    "fecha": ["fecha","fecha_factura","f_factura"],
    "cliente": ["razon_social","razon_soci","cliente"],
    "marca": ["clave_venta","clave-venta","marca"],
    "clave_producto": ["clave_producto","sku","codigo","producto"],
    "cantidad": ["cantidad","cant","qty"],
    "unidad": ["unidad","uom"],
    "moneda": ["moneda"],
    "tc": ["tc","t_c","tipo_de_cambio"],
    "total_usd_sin_iv": ["total_usd_sin_iv","total_usd_sin_iva","total_usd"],
    "importe": ["importe","monto","total_linea","total_sin_iva"]
}

def _find_col(df, names):
    for n in names:
        if n in df.columns: return n
    return None

# ✅ Limpieza numérica robusta
def _clean_money(series: pd.Series) -> pd.Series:
    s = (series.astype(str)
               .str.strip()
               .str.replace(r"[,$]", "", regex=True)
               .str.replace(" ", "", regex=False)
               .replace({
                   "#N/D": None, "N/D": None, "": None,
                   "-": None, "—": None, "–": None,
                   "nan": None, "NaN": None, "None": None, "none": None,
                   "NULL": None, "null": None,
                   "True": None, "False": None,
                   "true": None, "false": None
               }))
    return pd.to_numeric(s, errors="coerce")

def load_hoja3_to_df(path_excel_or_buffer, sheet=2):
    df = pd.read_excel(path_excel_or_buffer, sheet_name=sheet, dtype=str)
    df.columns = [_norm(c) for c in df.columns]

    cols = {k: _find_col(df, v) for k,v in ALIASES.items()}
    req = ["factura","fecha","cliente","clave_producto","cantidad"]
    missing = [r for r in req if not cols.get(r)]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en la hoja: {missing}")

    use_cols = {k: cols[k] for k in cols if cols[k]}
    dx = df[list(use_cols.values())].rename(columns={v:k for k,v in use_cols.items()})

    # fecha ISO + anio/mes
    dx["fecha"] = pd.to_datetime(dx["fecha"], errors="coerce")
    dx["anio"] = dx["fecha"].dt.year
    dx["mes"]  = dx["fecha"].dt.month
    dx["fecha"] = dx["fecha"].dt.strftime("%Y-%m-%d")

    # numéricos
    if "cantidad" in dx: dx["cantidad"] = _clean_money(dx["cantidad"])
    if "tc" in dx: dx["tc"] = _clean_money(dx["tc"])

    # importe_usd
    if "total_usd_sin_iv" in dx.columns:
        dx["importe_usd"] = _clean_money(dx["total_usd_sin_iv"])
    else:
        if "importe" not in dx.columns or "moneda" not in dx.columns:
            raise ValueError("No hay 'total_usd_sin_iv' ni la combinación (importe + moneda) para convertir.")
        dx["importe_local"] = _clean_money(dx["importe"])

        def to_usd(row):
            mon = (row.get("moneda") or "").upper()
            val = row.get("importe_local")
            tc  = row.get("tc") or 0
            if pd.isna(val):
                return None
            if mon in ("USD", "$", "DLS"):
                return val
            return (val / tc) if tc and tc != 0 else None

        dx["importe_usd"] = dx.apply(to_usd, axis=1)

    for c in ["orden_compra","marca","unidad","moneda","tc"]:
        if c not in dx.columns: dx[c] = None

    dx["sublinea"] = dx["clave_producto"]

    out = dx[[
        "fecha","anio","mes",
        "factura","orden_compra","cliente",
        "marca","sublinea","clave_producto",
        "cantidad","unidad","importe_usd","moneda","tc"
    ]].copy()

    out = out.rename(columns={"moneda": "moneda_origen"})

    def mkhash(r):
        key = "|".join([
            str(r.get("fecha","")),
            str(r.get("factura","")),
            str(r.get("clave_producto","")),
            str(r.get("cantidad","")),
            str(r.get("importe_usd","")),
            str(r.get("cliente","")),
        ])
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    out["hash_row"] = out.apply(mkhash, axis=1)
    out["importe_usd"] = pd.to_numeric(out["importe_usd"], errors="coerce")

    # ✅ Evitar nombres de columna duplicados (p.ej., 'cliente' repetida)
    out = out.loc[:, ~out.columns.duplicated(keep="first")]

    return out

def insert_ventas_items(df_items: pd.DataFrame, db_path=DB_PATH):
    if df_items.empty: return (0,0)
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()
        cur.execute("""
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
        cur.executemany("""
        INSERT OR IGNORE INTO ventas_items
        (fecha, anio, mes, factura, orden_compra, cliente, marca, sublinea, clave_producto,
         cantidad, unidad, importe_usd, moneda_origen, tc, hash_row)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, df_items[[
            "fecha","anio","mes","factura","orden_compra","cliente","marca","sublinea","clave_producto",
            "cantidad","unidad","importe_usd","moneda_origen","tc","hash_row"
        ]].where(pd.notna(df_items), None).values.tolist())
        con.commit()
        insertados = cur.rowcount if cur.rowcount is not None else 0
    ignorados = len(df_items) - max(insertados,0)
    return (max(insertados,0), max(ignorados,0))
