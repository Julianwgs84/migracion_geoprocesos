# -*- coding: utf-8 -*-
import arcpy
import sys
import traceback


def calcular_rutas_eta_prod(view_points_for_eta, nr_stops_target, colombia_streets_nd):
    arcpy.env.overwriteOutput = True

    try:
        arcpy.AddMessage("Iniciando cálculo de ETA...")

        # ==========================================
        # 1. EXTRACCIÓN DE RUTAS ÚNICAS
        # ==========================================
        iterator_field = "Name"
        valores_unicos = set()

        arcpy.AddMessage(f"Extrayendo valores únicos por el campo: {iterator_field}...")
        with arcpy.da.SearchCursor(view_points_for_eta, [iterator_field]) as cursor:
            for row in cursor:
                if row[0]:
                    valores_unicos.add(row[0])

        if not valores_unicos:
            arcpy.AddWarning("La vista de paradas no retornó información para procesar.")
            return False

        arcpy.AddMessage(f"Se identificaron {len(valores_unicos)} rutas a evaluar.")

        # ==========================================
        # 2. CICLO DE ANÁLISIS DE RUTAS
        # ==========================================
        for valor_actual in valores_unicos:
            arcpy.AddMessage(f"Procesando análisis para la ruta: {valor_actual}")

            filtered_layer = "Puntos_Filtrados"
            if isinstance(valor_actual, str):
                where_clause = f"{iterator_field} = '{valor_actual}'"
            else:
                where_clause = f"{iterator_field} = {valor_actual}"

            arcpy.management.MakeTableView(view_points_for_eta, filtered_layer, where_clause)

            route_layer_name = f"Route_{valor_actual}"

            try:
                route_layer_obj = arcpy.na.MakeRouteLayer(
                    in_network_dataset=colombia_streets_nd,
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
                    target=nr_stops_target,
                    schema_type="NO_TEST"
                )

                arcpy.AddMessage(f"Ruta {valor_actual} consolidada correctamente.")

            except arcpy.ExecuteError:
                arcpy.AddWarning(f"Error al procesar la ruta {valor_actual}: {arcpy.GetMessages(2)}")
            except Exception as e:
                arcpy.AddWarning(f"Error inesperado en la ruta {valor_actual}: {str(e)}")

        arcpy.AddMessage("Proceso de cálculo ETA finalizado para todas las rutas.")
        return True

    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        return False
    except Exception as e:
        arcpy.AddError(f"Error de sistema inesperado: {str(e)}")
        arcpy.AddError(traceback.format_exc())
        return False


if __name__ == '__main__':
    # --- Opción A: Rutas estáticas para pruebas locales (activa por defecto) ---
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"
    p_view_points  = fr"{ruta_raiz}\View_NA_PointStopsForETA"
    p_stops_target = fr"{ruta_raiz}\NR_STOPS"
    p_nd           = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Colombia.gdb\Colombia_Streets\Colombia_Streets_ND"

    # --- Opción B: Parámetros desde Toolbox (descomentar al registrar como Script Tool) ---
    # p_view_points  = arcpy.GetParameterAsText(0)
    # p_stops_target = arcpy.GetParameterAsText(1)
    # p_nd           = arcpy.GetParameterAsText(2)

    # --- Opción C: Parámetros por línea de comandos (descomentar para sys.argv) ---
    # p_view_points  = sys.argv[1]
    # p_stops_target = sys.argv[2]
    # p_nd           = sys.argv[3]

    calcular_rutas_eta_prod(p_view_points, p_stops_target, p_nd)
