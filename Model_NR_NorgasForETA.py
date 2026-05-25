# -*- coding: utf-8 -*-
import arcpy
import sys


# Script  para el cálculo de rutas para ETA iterando por el campo especificado y anexando los resultados.
# Se ajustaron las rutas a local para pruebas y se optimizó el código generado por ModelBuilder

def model_nr_norgas_for_eta(nd_path, points_path, target_stops, iter_field):
    """
    Script migrado: Calcula rutas para ETA iterando por el campo especificado 
    y anexa los resultados.
    """
    # Permitir sobrescribir salidas
    arcpy.env.overwriteOutput = True
    
    arcpy.AddMessage("Iniciando el cálculo de rutas...")

    # 1. REEMPLAZO DEL ITERADOR (Iterate Row Selection)
    # Obtener valores únicos por los cuales iterar, saltando valores nulos 
    unique_values = set()
    with arcpy.da.SearchCursor(points_path, [iter_field]) as cursor:
        for row in cursor:
            if row[0] is not None and str(row[0]).strip() != "": 
                unique_values.add(row[0])

    if not unique_values:
        arcpy.AddWarning("No se encontraron valores válidos para iterar.")
        return

    # 2. Ciclo de procesamiento para cada valor único agrupado (Name)
    for value in unique_values:
        arcpy.AddMessage(f"Procesando bloque (Name): {value}")
        
        # Crear la cláusula SQL para filtrar (Iterate Row Selection).
        where_clause = f"{iter_field} = '{value}'"
        filtered_layer = "Points_Filtered_Lyr"
        
        # Seleccionar las filas correspondientes a este valor
        arcpy.management.MakeTableView(points_path, filtered_layer, where_clause)

        # Nombre de la capa de análisis de red en memoria
        route_layer_name = f"Route_ETA_{value}"

        try:
            # Proceso: Make Route Layer (Crea la capa de análisis de rutas)
            route_layer_obj = arcpy.na.MakeRouteLayer(
                in_network_dataset=nd_path, 
                out_network_analysis_layer=route_layer_name, 
                impedance_attribute="TravelTime", 
                find_best_order="FIND_BEST_ORDER", 
                ordering_type="PRESERVE_FIRST", 
                accumulate_attribute_name=["Kilometers", "TravelTime"], 
                UTurn_policy="ALLOW_DEAD_ENDS_ONLY", 
                hierarchy="USE_HIERARCHY"
            )[0]

            # Proceso: Add Locations (Agrega las filas filtradas como paradas)
            arcpy.na.AddLocations(
                in_network_analysis_layer=route_layer_obj, 
                sub_layer="Stops", 
                in_table=filtered_layer, 
                field_mappings="Name Name #;RouteName RouteName #;TimeWindowStart TimeWindowStart #;TimeWindowEnd TimeWindowEnd #;CurbApproach CurbApproach 0;Attr_Length Attr_Length 0;LocationType LocationType 0;Attr_Travel_Time Attr_Travel_Time 0", 
                search_tolerance="5000 Meters"
            )

            # Proceso: Solve (Resuelve la ruta)
            arcpy.na.Solve(
                in_network_analysis_layer=route_layer_obj, 
                ignore_invalids="SKIP", 
                terminate_on_solve_error="CONTINUE"
            )

            # 3. REEMPLAZO DE SELECT DATA: Acceder a la subcapa 'Stops'
            # En arcpy, las subcapas de Network Analyst se referencian usando la barra invertida \
            orders_out_sublayer = f"{route_layer_name}\\Stops"

            # Proceso: Append (Anexar la subcapa a la base de datos origen)
            arcpy.management.Append(
                inputs=[orders_out_sublayer], 
                target=target_stops, 
                schema_type="TEST", 
                subtype="1297"
            )
            
            arcpy.AddMessage(f"Bloque {value} calculado y anexado correctamente.")

        except Exception as e:
            arcpy.AddWarning(f"Error procesando el bloque {value}: {str(e)}")
            
        finally:
            # Limpieza de memoria para evitar bloqueos en la siguiente iteración
            if arcpy.Exists(filtered_layer):
                arcpy.management.Delete(filtered_layer)
            if arcpy.Exists(route_layer_name):
                arcpy.management.Delete(route_layer_name)

    arcpy.AddMessage("Proceso finalizado.")

if __name__ == '__main__':
    # =========================================================================
    # CONFIGURACIÓN DE RUTAS ESTÁTICAS (Actual)
    # =========================================================================
    # Estas son las rutas que exportaste del modelo original.
    colombia_streets_nd = r"C:\Users\Administrator\Desktop\IntelligisDocuments\NetworkDataset\Colombia.gdb\Colombia_Streets\Colombia_Streets_ND"
    view_points_for_eta = r"C:\Users\Administrator\AppData\Roaming\ESRI\Desktop10.8\ArcCatalog\NorgasQA.sde\norgasqa.dbo.View_NA_PointStopsForETA"
    nr_stops_source = r"Database Connections\NorgasQA.sde\norgasqa.dbo.NR_STOPS"
    
    # Campo definido en el Iterate Row Selection
    campo_iterador = "Name" 

    # Llamada a la función con las variables estáticas
    model_nr_norgas_for_eta(colombia_streets_nd, view_points_for_eta, nr_stops_source, campo_iterador)

    # =========================================================================
    # CONFIGURACIÓN PARA TOOLBOX 
    # =========================================================================
    # líneas estáticas superiores (desde la 71 a la 80) se pueden comentar y descomentar para ejecutar el script directamente o a través de una herramienta en ArcGIS Pro.
    # colombia_streets_nd = sys.argv[1] # Parámetro 1: Network Dataset
    # view_points_for_eta = sys.argv[2] # Parámetro 2: Tabla/Vista de puntos (Input Table)
    # nr_stops_source = sys.argv[3]     # Parámetro 3: Destino (Target Dataset)
    # campo_iterador = sys.argv[4]      # Parámetro 4: Campo de agrupación ('Name')
    
    # model_nr_norgas_for_eta(colombia_streets_nd, view_points_for_eta, nr_stops_source, campo_iterador)