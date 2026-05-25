# Proyecto Automata-Data — Pipeline DataOps de 4 Etapas
**ITY1101 Gestión de Datos para IA | Parcial N°2 | DuocUC**

Repositorio GitHub: `https://github.com/<usuario>/automata-data-pipeline`
*(reemplazar `<usuario>` por el usuario real del equipo)*

---

## Descripción

Pipeline DataOps de cuatro etapas (Ingesta → Limpieza → Validación → Carga) con dashboard de orquestación en Flask y persistencia en Supabase (PostgreSQL en la nube). El caso de negocio es **TechIndustry SpA**, empresa B2B que vende maquinaria y repuestos industriales (motores eléctricos, sensores, bombas, automatización). Implementa principios DataOps: trazabilidad por logs, separación de datos crudos/procesados/validados/inválidos, idempotencia mediante `upsert`, y monitoreo de KPIs de calidad de datos.

Sobre la salida del pipeline (los datos ya cargados) se monta una **capa de visualización / BI** que entrega un dashboard con gráficos y exportación de informes. Esta capa es de *consumo*, no una quinta etapa del ETL: el pipeline sigue siendo de cuatro fases.

---

## Estructura del Proyecto

```
pipeline-ingesta/
├── origen/
│   └── ventas.csv              # dataset fuente (20 registros, no se modifica)
├── data/
│   ├── raw/                    # archivos ingestados con timestamp
│   ├── processed/              # archivos tras limpieza
│   ├── validated/              # archivos que pasaron validación
│   └── invalid/                # filas rechazadas por validación
├── logs/                       # logs diarios por ejecución
├── templates/
│   ├── index.html              # dashboard de orquestación del pipeline + CRUD
│   ├── dashboard.html          # visualización BI (KPIs + gráficos Chart.js)
│   └── informe_export.html     # informe ejecutivo imprimible (PDF)
├── ingesta.py                  # Etapa 1
├── limpieza.py                 # Etapa 2
├── validacion.py               # Etapa 3
├── carga.py                    # Etapa 4 (Supabase)
├── app.py                      # Dashboard Flask + CRUD
├── Dockerfile                  # contenedor para despliegue
├── .env.example                # plantilla de credenciales
├── .gitignore                  # excluye .env, __pycache__, logs, data
└── informe_tecnico.html        # informe técnico del proyecto
```

---

## Requisitos

- Python 3.10+ (solo módulos estándar + Flask)
- Cuenta Supabase con tabla `ventas` creada
- Docker (opcional, para despliegue containerizado)

---

## Configuración de Credenciales (IMPORTANTE)

Por cumplimiento de la **Ley 21.719 de Protección de Datos Personales** (Chile), las credenciales **no están embebidas en el código fuente**. Antes de ejecutar el proyecto:

1. Copiar la plantilla de variables de entorno:
   ```bash
   cp .env.example .env
   ```

2. Editar `.env` y completar con las credenciales reales de Supabase:
   ```
   SUPABASE_URL=https://<su-proyecto>.supabase.co
   SUPABASE_KEY=<su-api-key>
   ```

3. Exportar las variables al ambiente:
   ```bash
   export $(grep -v '^#' .env | xargs)
   ```

Si las variables no están definidas, los scripts abortan con un error explícito en lugar de continuar inseguro.

---

## Cómo ejecutar

### Opción A — Local

```bash
pip install flask
export $(grep -v '^#' .env | xargs)
python3 app.py
```

Acceder al dashboard en `http://localhost:5000`.

### Opción B — Docker

```bash
docker build -t automata-data .
docker run -p 5000:5000 \
  -e SUPABASE_URL="$SUPABASE_URL" \
  -e SUPABASE_KEY="$SUPABASE_KEY" \
  automata-data
```

### Ejecución por etapa (sin dashboard)

```bash
python3 ingesta.py     # Etapa 1
python3 limpieza.py    # Etapa 2
python3 validacion.py  # Etapa 3
python3 carga.py       # Etapa 4
```

---

## Etapas del Pipeline

| Etapa | Script | Entrada | Salida | Responsabilidad |
|-------|--------|---------|--------|-----------------|
| 1. Ingesta | `ingesta.py` | `origen/ventas.csv` | `data/raw/ventas_raw_<ts>.csv` | Copia con timestamp, log estructurado |
| 2. Limpieza | `limpieza.py` | `data/raw/` | `data/processed/` | Normaliza fechas, deduplica por ID, formatea texto |
| 3. Validación | `validacion.py` | `data/processed/` | `data/validated/` + `data/invalid/` | Chequeos estructurales y semánticos |
| 4. Carga | `carga.py` | `data/validated/` | Tabla `ventas` en Supabase | Upsert por lotes con `merge-duplicates` |

---

## Capa de Visualización (BI)

Sobre los datos ya cargados se ofrece una capa de consumo accesible desde el dashboard. **No es una etapa del pipeline** (este sigue siendo de 4 fases): solo lee la tabla `ventas` de Supabase y la presenta.

| Ruta | Qué hace |
|------|----------|
| `/dashboard` | KPIs (ingresos, unidades, ticket promedio) + 4 gráficos: ingresos por categoría, por región, evolución temporal y top productos (Chart.js) |
| `/exportar/csv` | Descarga todos los registros de la BD como CSV |
| `/exportar/informe` | Genera un informe ejecutivo imprimible (Ctrl+P → guardar como PDF) con KPIs, ranking de vendedores y detalle de transacciones |

Se accede desde el botón "Ver dashboard y gráficos" en la página principal.

---

## KPIs de Monitoreo (resumen)

| # | KPI | Fórmula | Umbral |
|---|-----|---------|--------|
| 1 | Tasa de Completitud | `(registros_no_nulos / total) × 100` | ≥ 95% |
| 2 | Tasa de Validez | `(registros_validos / total) × 100` | ≥ 98% |
| 3 | Tasa de Duplicados | `(duplicados / total) × 100` | ≤ 2% |
| 4 | Latencia del Pipeline | `t_fin - t_inicio` (s) | ≤ 60s |
| 5 | Registros Cargados | `count(inserts_ok)` | ≥ 18/20 |
| 6 | Tasa de Error de Carga | `(errores_lote / total_lotes) × 100` | ≤ 1% |

Detalle completo en `informe_tecnico.html` sección 7.

---

## Dataset utilizado

`origen/ventas.csv` contiene 20 registros de ventas de maquinaria y repuestos industriales (motores, sensores, bombas, repuestos, automatización) con los campos: `id`, `fecha`, `producto`, `categoria`, `cantidad`, `precio_unitario`, `vendedor`, `region`.

---

## Control de versiones y equipo

- **Repositorio**: GitHub (rama `main`, commits por etapa para trazabilidad)
- **Coordinación**: división de responsabilidades por módulo (un integrante por etapa del pipeline)
- **Trazabilidad**: cada ejecución deja log en `logs/log_YYYYMMDD.txt`
