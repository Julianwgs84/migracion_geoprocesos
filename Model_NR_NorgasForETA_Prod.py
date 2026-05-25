# -*- coding: utf-8 -*-
import arcpy
import sys
import traceback

# Script refactorizado para el cálculo de ETA (Estimated Time of Arrival)
# Se adaptaron las rutas al entorno local y se implementó la iteración no exportada por ModelBuilder

def procesar_rutas_eta():
    # Se habilita la sobreescritura de salidas para prevenir bloqueos de esquema
    arcpy.env.overwriteOutput = True
    
    # ==========================================
    # 1. RUTAS LOCALES PARA PRUEBAS
    # ==========================================
    # Referencia a la File Geodatabase local
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"
    
    view_points_for_eta = fr"{ruta_raiz}\View_NA_PointStopsForETA"
    nr_stops_target = fr"{ruta_raiz}\NR_STOPS"
    
    # Referencia local al dataset de red
    colombia_streets_nd = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Colombia.gdb\Colombia_Streets\Colombia_Streets_ND"
    
    try:
        arcpy.AddMessage("Iniciando ejecución del geoproceso de cálculo de ETA...")
        
        # ==========================================
        # 2. REEMPLAZO DEL ITERADOR DE MODEL BUILDER
        # ==========================================
        # Se obtiene una lista de rutas únicas de forma programática mediante cursor
        iterator_field = "Name" 
        valores_unicos = set()
        
        arcpy.AddMessage(f"Extrayendo valores únicos mediante el campo: {iterator_field}...")
        with arcpy.da.SearchCursor(view_points_for_eta, [iterator_field]) as cursor:
            for row in cursor:
                if row[0]:
                    valores_unicos.add(row[0])
                    
        if not valores_unicos:
            arcpy.AddWarning("La vista de paradas no retornó información para procesar el ETA.")
            return False

        arcpy.AddMessage(f"Se identificaron {len(valores_unicos)} rutas a evaluar.")

        # ==========================================
        # 3. CICLO DE ANÁLISIS DE RUTAS (ETA)
        # ==========================================
        for valor_actual in valores_unicos:
            arcpy.AddMessage(f"\nProcesando análisis para la ruta: {valor_actual}")
            
            # Se aplica filtro individual de puntos correspondientes a la ruta en curso
            filtered_layer = "Puntos_Filtrados"
            if isinstance(valor_actual, str):
                where_clause = f"{iterator_field} = '{valor_actual}'"
            else:
                where_clause = f"{iterator_field} = {valor_actual}"
                
            arcpy.management.MakeFeatureLayer(view_points_for_eta, filtered_layer, where_clause)
            
            # Se inicializa la capa de Route Analysis
            route_layer_name = f"Route_ETA_{valor_actual}"
            route_result = arcpy.na.MakeRouteLayer(
                in_network_dataset=colombia_streets_nd,
                out_network_analysis_layer=route_layer_name,
                impedance_attribute="TravelTime",
                find_best_order="FIND_BEST_ORDER",
                ordering_type="PRESERVE_FIRST",
                accumulate_attribute_name=["Kilometers", "TravelTime"],
                UTurn_policy="ALLOW_DEAD_ENDS_ONLY",
                hierarchy="USE_HIERARCHY"
            )
            route_layer = route_result[0]
            
            # Se identifica la subcapa de paradas (Stops)
            sub_layer_names = arcpy.na.GetNAClassNames(route_layer)
            stops_sublayer_name = sub_layer_names["Stops"]
            
            # Se integran las paradas filtradas a la capa de red
            arcpy.na.AddLocations(
                in_network_analysis_layer=route_layer,
                sub_layer=stops_sublayer_name,
                in_table=filtered_layer,
                field_mappings="Name Name #;RouteName RouteName #;TimeWindowStart TimeWindowStart #;TimeWindowEnd TimeWindowEnd #;CurbApproach CurbApproach 0;Attr_Length Attr_Length 0;LocationType LocationType 0;Attr_Travel_Time Attr_Travel_Time 0",
                search_tolerance="5000 Meters",
                append="CLEAR"
            )
            
            # Ejecución del solver de ruta
            try:
                arcpy.AddMessage(f"  Resolviendo geometría de red para: {valor_actual}...")
                arcpy.na.Solve(
                    in_network_analysis_layer=route_layer,
                    ignore_invalids="SKIP",
                    terminate_on_solve_error="CONTINUE"
                )
            except arcpy.ExecuteError:
                # Se registra la falla de enrutamiento y se continúa con el siguiente grupo para evitar interrupción total
                arcpy.AddWarning(f"  Fallo durante la resolución de ruta {valor_actual}: {arcpy.GetMessages(2)}")
                continue

            # ==========================================
            # 4. EXTRACCIÓN Y CONSOLIDACIÓN DE RESULTADOS
            # ==========================================
            if arcpy.GetInstallInfo()['ProductName'] == 'Desktop':
                stops_sublayer = arcpy.mapping.ListLayers(route_layer, stops_sublayer_name)[0]
            else: # Entorno ArcGIS Pro
                stops_sublayer = route_layer.listLayers(stops_sublayer_name)[0]
            
            arcpy.AddMessage(f"  Anexando resultados calculados en tabla NR_STOPS...")
            arcpy.management.Append(
                inputs=[stops_sublayer],
                target=nr_stops_target,
                schema_type="TEST",
                subtype="1297"
            )
            
            # Se elimina la referencia a capas temporales para liberar memoria RAM en cada iteración
            arcpy.management.Delete(filtered_layer)
            arcpy.management.Delete(route_layer)

        arcpy.AddMessage("\nProceso de ETA finalizado exitosamente.")
        return True

    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        return False
    except Exception as e:
        arcpy.AddError(f"Error de sistema inesperado: {str(e)}")
        arcpy.AddError(traceback.format_exc())
        return False

if __name__ == '__main__':
    procesar_rutas_eta()