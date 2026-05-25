# Migración Geoprocesos

Repositorio de scripts de geoprocesos en Python para ArcGIS Pro, orientados a análisis de **Closest Facility (CF)**, **ETA** y **Vehicle Routing Problem (VRP)**.

## Propósito

Este repositorio reúne scripts desarrollados con `arcpy` para ejecutar análisis espaciales y operativos que antes estaban organizados en modelos visuales. El objetivo principal es contar con procesos más claros, mantenibles y listos para pruebas, ajuste funcional y futura publicación como herramientas o servicios de geoprocesamiento.

## Estructura general

Los scripts incluidos siguen una línea de estilo unificada para facilitar su lectura y mantenimiento:

- Comentarios técnicos en español, con redacción natural y consistente.
- Bloques organizados por secciones lógicas.
- Manejo de entradas en tres modalidades:
  - rutas estáticas para pruebas locales;
  - parámetros para uso en Toolbox, comentados para activarse cuando corresponda;
  - parámetros por línea de comandos con `sys.argv[...]`, también comentados.

## Scripts incluidos

| Script | Descripción |
|---|---|
| `Model_CF_Norgas_PROD_with_FactorTraffic_MultipleMunicipalityAndDriveTimeAndFilterDriverCancellingOrder.py` | Ejecuta un análisis Closest Facility para identificar conductores candidatos bajo reglas operativas de tráfico, municipio, tiempo de recorrido y exclusión de conductores con cancelación de orden. |
| `Model_CF_Norgas_QA_with_FactorTraffic_V1.py` | Ejecuta la variante QA del análisis Closest Facility con lógica de tráfico y selección de conductores viables para pruebas y validación funcional. |
| `Model_NR_NorgasForETA.py` | Calcula rutas y tiempos estimados de llegada para el flujo ETA de Norgas, recorriendo registros de entrada y consolidando resultados de red por cada caso evaluado. |
| `Model_NR_NorgasForETA_Prod.py` | Ejecuta la versión productiva del cálculo ETA con estructura orientada a operación estable y resultados preparados para consumo posterior. |
| `Model_VRP_ImpadoelWithProject_D1.py` | Resuelve un modelo Vehicle Routing Problem para el grupo D1, integrando órdenes, depósitos, vehículos y especialidades, con salida proyectada a WGS84. |
| `Model_VRP_ImpadoelWithProject_D2.py` | Resuelve el modelo VRP del grupo D2 con la misma base operativa de D1, ajustando los insumos correspondientes al conjunto de órdenes y su configuración particular. |
| `Model_VRP_ImpadoelWithProject_D3.py` | Resuelve el modelo VRP del grupo D3, manteniendo la lógica de carga de localizaciones y resolución de rutas para su conjunto específico de órdenes. |
| `Model_V01_GPF_Truck_Full_Prod_version4.py` | Ejecuta un flujo VRP completo para GPF en ambiente productivo, iterando vehículos, cargando restricciones operativas y consolidando resultados, violaciones y visitas a depósito. |
| `Model_V01_GPF_Truck_Full_Dev_version7.py` | Ejecuta la versión de desarrollo del proceso VRP GPF, útil para pruebas controladas, ajustes funcionales y validación del flujo antes de promover cambios. |

## Modalidades de entrada

Cada script está preparado para trabajar con tres esquemas de parametrización.

### 1. Rutas estáticas

Se usan por defecto para pruebas locales. Normalmente están activas al inicio del script y apuntan a rutas tipo:

```python
ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"
```

### 2. Parámetros para Toolbox

Se dejan comentados para habilitarlos cuando el script se registre como **Script Tool** en ArcGIS Pro.

```python
# entrada_1 = arcpy.GetParameterAsText(0)
# entrada_2 = arcpy.GetParameterAsText(1)
```

### 3. Parámetros por línea de comandos

También se dejan comentados para habilitarlos cuando se requiera ejecutar el script desde consola o mediante un flujo externo.

```python
# entrada_1 = sys.argv[1]
# entrada_2 = sys.argv[2]
```

## Convención recomendada de uso

Para evitar ambigüedad en pruebas y despliegues, se recomienda usar una sola modalidad de entrada por ejecución:

- **Pruebas locales**: dejar activas las rutas estáticas.
- **Toolbox en ArcGIS Pro**: descomentar `arcpy.GetParameterAsText(...)` y comentar las rutas estáticas.
- **Ejecución externa o automatizada**: descomentar `sys.argv[...]` y comentar las demás opciones.

## Requisitos generales

Para ejecutar estos scripts se recomienda contar con:

- ArcGIS Pro con licencia compatible con las herramientas utilizadas.
- Extensión **Network Analyst** cuando el proceso involucre CF, ETA o VRP.
- Acceso a geodatabases, datasets de red y tablas asociadas según cada flujo.
- Entorno Python de ArcGIS Pro con `arcpy` disponible.

## Organización sugerida del repositorio

Una forma práctica de mantener este repositorio es la siguiente:

```text
migracion_geoprocesos/
├── README.md
├── Model_CF_Norgas_PROD_with_FactorTraffic_MultipleMunicipalityAndDriveTimeAndFilterDriverCancellingOrder.py
├── Model_CF_Norgas_QA_with_FactorTraffic_V1.py
├── Model_NR_NorgasForETA.py
├── Model_NR_NorgasForETA_Prod.py
├── Model_VRP_ImpadoelWithProject_D1.py
├── Model_VRP_ImpadoelWithProject_D2.py
├── Model_VRP_ImpadoelWithProject_D3.py
├── Model_V01_GPF_Truck_Full_Prod_version4.py
└── Model_V01_GPF_Truck_Full_Dev_version7.py
```

## Recomendaciones de mantenimiento

- Mantener la misma estructura de comentarios y secciones en scripts nuevos.
- Documentar cambios funcionales importantes en los mensajes de commit.
- Evitar mezclar estilos de nombres dentro de un mismo archivo.
- Validar rutas, nombres de capas temporales y salidas antes de promover cambios a ambientes más estables.
- Cuando un script tenga versión de desarrollo y productiva, procurar que ambas conserven una base estructural similar para facilitar comparación y soporte.

## Commit sugerido

```text
refactor: unifica estilo y configuración de entrada en 9 scripts de geoprocesos
```

## Nota final

Este repositorio está orientado a centralizar scripts operativos de geoprocesamiento con una estructura más homogénea, clara y sostenible para mantenimiento técnico.
