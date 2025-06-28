
# 📊 Módulo: `main/heatmap_ventas.py` – Heatmap de Ventas con Secuencialidad y Crecimiento YoY

Este README documenta exclusivamente el archivo:

```
main/heatmap_ventas.py
```

---

## ✅ Descripción general

Este módulo genera un **heatmap visual de ventas por línea de negocio**, aplicando:

- **Secuencialidad basada en `periodo_id`** (formato año.mes, año.trimestre o año según el caso)
- **Comparación de crecimiento Year-over-Year (YoY)**
- **Formato financiero con dos decimales**
- **Contraste dinámico en las anotaciones según intensidad del color**
- **Exportación de la tabla final a Excel**

---

## ✅ Características clave:

- **Visualización cronológica de ventas** ordenada por `periodo_id`
- **Eje Y en el heatmap con formato:**  
`"periodo_id - periodo"`  
Ejemplo: `"23.01 - Ene-2023"`
- **Color del heatmap:** Verde (`cmap="Greens"`)
- **Formato de moneda:** `$X,XXX.XX` con dos decimales
- **Tamaño de fuente de anotaciones:** 8 pts
- **Contraste automático:**  
Texto en blanco si la intensidad del color de fondo supera el 60%
- **Detección de nuevas ventas:**  
Las celdas sin ventas en el periodo anterior se marcan como `"NEW"`

---

## ✅ Tipos de análisis soportados:

- **Mensual**
- **Trimestral**
- **Anual**
- **Rango Personalizado** (sin cálculo de % crecimiento)

---

## ✅ Lógica de cálculo de crecimiento (%):

- **Para Mensual:**  
Enero-2024 vs Enero-2023, Febrero-2024 vs Febrero-2023, etc.

- **Para Trimestral:**  
Q2-2025 vs Q2-2024, Q3-2025 vs Q3-2024, etc.

- **Para Anual:**  
2025 vs 2024, 2024 vs 2023, etc.

> El cálculo es siempre **Year-over-Year dentro del mismo tipo de periodo**.

---

## ✅ Requisitos mínimos del DataFrame de entrada:

El DataFrame debe contener como mínimo:

- Una columna de **Fecha** (`datetime`)
- Una columna de **Línea de negocio** (flexible: `"linea_prodcucto"`, `"linea_producto"`, `"linea_de_negocio"`, etc.)
- Una columna de **Importe** (flexible: `"valor mn"`, `"importe"`, `"valor_usd"`, etc.)

El módulo incluye detección flexible de nombres de columnas mediante la función `detectar_columna()`.

---

## ✅ Ejemplo de uso:

```python
from main import heatmap_ventas

# Suponiendo que ya tienes un DataFrame df con las columnas necesarias:
heatmap_ventas.run(df)
```

---

## ✅ Exportación:

Al finalizar, el módulo genera una tabla Excel lista para descarga, bajo el nombre:

```
heatmap_filtrado.xlsx
```

---

## ✅ Próximos posibles ajustes (Roadmap):

- Permitir al usuario cambiar entre comparación YoY vs secuencial
- Exportación del heatmap como imagen `.png`
- Personalización del umbral de contraste vía la interfaz
- Filtros adicionales por canal o región
