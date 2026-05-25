# -*- coding: utf-8 -*-
import arcpy
import sys
import traceback


def calcular_rutas_eta(nd_path, points_path, target_stops, iter_field):
    arcpy.env.overwriteOutput = True

    arcpy.AddMessage("Iniciando cálculo de rutas ETA...")

    # ==========================================
    # 1. EXTRACCIÓN DE VALORES ÚNICOS PARA ITERACIÓN
    # ==========================================
    valores_unicos = set()
    with arcpy.da.SearchCursor(points_path, [iter_field]) as cursor:
        for row in cursor:
            if row[0] is not None and str(row[0]).strip() != "":
                valores_unicos.add(row[0])

    if not valores_unicos:
        arcpy.AddWarning("No se encontraron valores válidos para iterar.")
        return

    # ==========================================
    # 2. CICLO DE CÁLCULO POR RUTA
    # ==========================================
    for valor in valores_unicos:
        arcpy.AddMessage(f"Procesando ruta: {valor}")

        where_clause   = f"{iter_field} = '{valor}'"
        filtered_layer = "Points_Filtered_Lyr"
        arcpy.management.MakeTableView(points_path, filtered_layer, where_clause)

        route_layer_name = f"Route_ETA_{valor}"

        try:
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

            arcpy.na.AddLocations(
                in_network_analysis_layer=route_layer_obj,
                sub_layer="Stops",
                in_table=filtered_layer,
                field_mappings="Name Name #;RouteName RouteName #",
                search_tolerance="5000 Meters",
                append="CLEAR"
            )

            arcpy.na.Solve(
                in_network_analysis_layer=route_layer_obj,
                ignore_invalids="SKIP",
                terminate_on_solve_error="CONTINUE"
            )

            if arcpy.GetInstallInfo()["ProductName"] == "Desktop":
                stops_layer = arcpy.mapping.ListLayers(route_layer_obj, "Stops")[0]
            else:
                stops_layer = route_layer_obj.listLayers("Stops")[0]

            arcpy.management.Append(
                inputs=stops_layer,
                target=target_stops,
                schema_type="NO_TEST"
            )

            arcpy.AddMessage(f"Ruta {valor} procesada y resultados consolidados.")

        except arcpy.ExecuteError:
            arcpy.AddWarning(f"Error al procesar la ruta {valor}: {arcpy.GetMessages(2)}")
        except Exception as e:
            arcpy.AddWarning(f"Error inesperado en la ruta {valor}: {str(e)}")

    arcpy.AddMessage("Proceso de cálculo ETA finalizado para todas las rutas.")


if __name__ == '__main__':
    # --- Opción A: Rutas estáticas para pruebas locales (activa por defecto) ---
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"
    p_nd_path      = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Colombia.gdb\Colombia_Streets\Colombia_Streets_ND"
    p_points_path  = fr"{ruta_raiz}\View_NA_PointStopsForETA"
    p_target_stops = fr"{ruta_raiz}\NR_STOPS"
    p_iter_field   = "Name"

    # --- Opción B: Parámetros desde Toolbox (descomentar al registrar como Script Tool) ---
    # p_nd_path      = arcpy.GetParameterAsText(0)
    # p_points_path  = arcpy.GetParameterAsText(1)
    # p_target_stops = arcpy.GetParameterAsText(2)
    # p_iter_field   = arcpy.GetParameterAsText(3)

    # --- Opción C: Parámetros por línea de comandos (descomentar para sys.argv) ---
    # p_nd_path      = sys.argv[1]
    # p_points_path  = sys.argv[2]
    # p_target_stops = sys.argv[3]
    # p_iter_field   = sys.argv[4]

    calcular_rutas_eta(p_nd_path, p_points_path, p_target_stops, p_iter_field)
