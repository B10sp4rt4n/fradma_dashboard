
# 🛠️ Fradma Dashboard - Módulo Heatmap Ventas (Normalización y Mapeo Robusto de Columnas)

## 📌 Propósito del módulo

El módulo `main/heatmap_ventas.py` genera un Heatmap interactivo para visualizar el desempeño de ventas por línea de negocio y periodo. Permite análisis por mes, trimestre, año o rango personalizado.

---

## ✅ Problema detectado durante despliegue

Los reportes fuente (X AGENTE, CONTPAQi u otros) presentan inconsistencias en el nombre de las columnas clave.  
Casos detectados:

| Campo lógico | Nombres reales encontrados en archivos |
|--------------|----------------------------------------|
| Línea de negocio | `linea_prodcucto`, `linea_producto`, `linea_de_negocio`, `linea producto`, `linea_de_producto` |
| Importe | `valor_mn`, `importe`, `valor_usd`, `valor mn` |

Esto provocaba errores en tiempo de ejecución porque la app no encontraba las columnas esperadas.

---

## ✅ Solución implementada: Mapeador robusto de columnas

Se implementó una capa de mapeo que:

- Permite detectar las columnas clave sin importar errores tipográficos menores, acentos o formatos inconsistentes.
- Es centralizada y fácil de mantener.
- Genera mensajes de error claros al usuario si no se encuentran columnas válidas.

---

### 📌 Estructura del mapeador

**Definición:**

```python
mapa_columnas = {
    "linea": ["linea_prodcucto", "linea_producto", "linea_de_negocio", "linea producto", "linea_de_producto"],
    "importe": ["valor_mn", "importe", "valor_usd", "valor mn"]
}
```

**Función de detección:**

```python
def detectar_columna(df, posibles_nombres):
    for posible in posibles_nombres:
        for col in df.columns:
            if unicodedata.normalize('NFKD', col.lower().strip()).encode('ascii', errors='ignore').decode('utf-8') == unicodedata.normalize('NFKD', posible.lower().strip()).encode('ascii', errors='ignore').decode('utf-8'):
                return col
    return None
```

---

### ✅ Flujo de trabajo

1. El archivo fuente se carga desde `app.py`.
2. El DataFrame (`df`) se pasa al módulo Heatmap vía:

```python
heatmap_ventas.run(st.session_state["df"])
```

3. Dentro del módulo Heatmap:

- Se limpian encabezados.
- Se detectan columnas usando el mapeador.
- Se valida y genera el Heatmap solo si ambas columnas (línea e importe) existen.

---

### ✅ Ventajas de este enfoque

| Ventaja | Beneficio |
|--------|----------|
| Escalable | Fácil de agregar nuevos nombres de columnas en el futuro |
| Mantenible | Código centralizado y limpio |
| Tolerante a errores | Permite flexibilidad ante errores de formato menores |
| Mejor UX | Mensajes claros si faltan columnas clave |

---

### ✅ Recomendación futura

- Centralizar el mapeador como módulo común para otros dashboards.
- Habilitar selección manual de columnas si se detectan múltiples coincidencias.
- Implementar pruebas unitarias sobre el mapeador.

---

### ✅ Commit recomendado para esta actualización:

```bash
git add main/heatmap_ventas.py
git add main/README_heatmap_column_mapping.md
git commit -m "🛠️ Mejora: Implementación de mapeador robusto de columnas para módulo Heatmap Ventas"
git push
```
