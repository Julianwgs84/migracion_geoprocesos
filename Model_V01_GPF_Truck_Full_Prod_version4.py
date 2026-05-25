# -*- coding: utf-8 -*-
import arcpy
import sys
import traceback


def optimizar_rutas_gpf(orders_out, routes_out, orders_violation_out, depots_visit_out):
    arcpy.env.overwriteOutput = True

    # ==========================================
    # 1. RUTAS Y FUENTES DE DATOS
    # ==========================================

    # --- Opción A: Rutas estáticas para pruebas locales (activa por defecto) ---
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"
    vehicles_source = fr"{ruta_raiz}\VRP_VEHICLE"
    orders_source = fr"{ruta_raiz}\View_VRP_ORDERS"
    network_dataset = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Ecuador.gdb\Ecuador\Ecuador_ND"
    specialties_source = fr"{ruta_raiz}\VRP_Specialtes_Name"
    breaks_source = fr"{ruta_raiz}\VRP_BREAKS"
    depots_source = fr"{ruta_raiz}\VRP_DEPOTS"
    renewals_source = fr"{ruta_raiz}\VRP_ROUTE_RENEWALS"
    orders_result_source = fr"{ruta_raiz}\VRP_ORDERS_RESULT"
    vehicles_result_source = fr"{ruta_raiz}\VRP_VEHICLE_RESULT"
    breaks_result_source = fr"{ruta_raiz}\VRP_BREAKS_RESULT"
    depot_visits_result_source = fr"{ruta_raiz}\VRP_DEPOT_VISITS_RESULT"
    orders_violations_result_source = fr"{ruta_raiz}\VRP_ORDERS_VIOLATIONS"

    # --- Opción B: Rutas desde Toolbox (descomentar al registrar como Script Tool) ---
    # vehicles_source = arcpy.GetParameterAsText(4)
    # orders_source = arcpy.GetParameterAsText(5)
    # network_dataset = arcpy.GetParameterAsText(6)
    # specialties_source = arcpy.GetParameterAsText(7)
    # breaks_source = arcpy.GetParameterAsText(8)
    # depots_source = arcpy.GetParameterAsText(9)
    # renewals_source = arcpy.GetParameterAsText(10)
    # orders_result_source = arcpy.GetParameterAsText(11)
    # vehicles_result_source = arcpy.GetParameterAsText(12)
    # breaks_result_source = arcpy.GetParameterAsText(13)
    # depot_visits_result_source = arcpy.GetParameterAsText(14)
    # orders_violations_result_source = arcpy.GetParameterAsText(15)

    # --- Opción C: Rutas por argumentos de línea de comandos (descomentar para sys.argv) ---
    # vehicles_source = sys.argv[5]
    # orders_source = sys.argv[6]
    # network_dataset = sys.argv[7]
    # specialties_source = sys.argv[8]
    # breaks_source = sys.argv[9]
    # depots_source = sys.argv[10]
    # renewals_source = sys.argv[11]
    # orders_result_source = sys.argv[12]
    # vehicles_result_source = sys.argv[13]
    # breaks_result_source = sys.argv[14]
    # depot_visits_result_source = sys.argv[15]
    # orders_violations_result_source = sys.argv[16]

    try:
        arcpy.AddMessage("Iniciando análisis VRP GPF...")

        # ==========================================
        # 2. VALIDACIÓN INICIAL
        # ==========================================
        row_count = int(arcpy.management.GetCount(orders_source)[0])
        if row_count == 0:
            arcpy.AddWarning("No se encontraron órdenes para procesar.")
            return False

        # ==========================================
        # 3. LISTA DE VEHÍCULOS A EVALUAR
        # ==========================================
        oid_field = arcpy.Describe(vehicles_source).OIDFieldName
        oid_values = []

        with arcpy.da.SearchCursor(vehicles_source, [oid_field]) as cursor:
            for row in cursor:
                if row[0] is not None:
                    oid_values.append(row[0])

        if not oid_values:
            arcpy.AddWarning("No se encontraron vehículos disponibles para procesar.")
            return False

        arcpy.AddMessage(f"Se identificaron {len(oid_values)} vehículos para análisis.")

        # ==========================================
        # 4. CICLO PRINCIPAL POR VEHÍCULO
        # ==========================================
        for oid_value in oid_values:
            vehicle_layer = "Vehicle_Iter_Layer"
            breaks_view = "Breaks_View"
            renewals_view = "Renewals_View"
            valid_orders_view = "Orders_Filtered"
            assigned_orders_layer = "Assigned_Orders_Layer"
            valid_routes_layer = "Valid_Routes_Layer"
            orders_violation_layer = "Orders_Violation_Layer"

            try:
                where_vehicle = f"{arcpy.AddFieldDelimiters(vehicles_source, oid_field)} = {oid_value}"
                arcpy.management.MakeFeatureLayer(vehicles_source, vehicle_layer, where_vehicle)

                route_name = None
                with arcpy.da.SearchCursor(vehicle_layer, ["Name"]) as cursor_vehicle:
                    for row_vehicle in cursor_vehicle:
                        route_name = row_vehicle[0]
                        break

                if not route_name:
                    arcpy.AddWarning(f"No fue posible obtener el nombre de ruta para el OBJECTID {oid_value}.")
                    arcpy.management.Delete(vehicle_layer)
                    continue

                arcpy.AddMessage(f"Procesando vehículo/ruta: {route_name}")

                # ==========================================
                # 5. CONFIGURACIÓN DE CAPA VRP
                # ==========================================
                vrp_layer_name = f"VRP_{route_name}"
                vrp_result = arcpy.na.MakeVehicleRoutingProblemLayer(
                    in_network_dataset=network_dataset,
                    out_network_analysis_layer=vrp_layer_name,
                    time_impedance="TravelTime",
                    distance_impedance="Kilometers",
                    distance_units="Meters",
                    default_date="14/06/2000 9:33:49 p. m.",
                    capacity_count=3,
                    time_window_factor="High",
                    excess_transit_factor="Low",
                    UTurn_policy="ALLOW_DEAD_ENDS_AND_INTERSECTIONS_ONLY"
                )
                vrp_layer = vrp_result[0]

                sub_layer_names = arcpy.na.GetNAClassNames(vrp_layer)
                specialties_name = sub_layer_names["Specialties"]
                routes_name = sub_layer_names["Routes"]
                orders_name = sub_layer_names["Orders"]
                seeds_name = sub_layer_names["RouteSeedPoints"]
                breaks_name = sub_layer_names["Breaks"]
                depots_name = sub_layer_names["Depots"]
                renewals_name = sub_layer_names["RouteRenewals"]
                depot_visits_name = sub_layer_names["DepotVisits"]

                # ==========================================
                # 6. CARGA DE LOCALIZACIONES
                # ==========================================
                arcpy.na.AddLocations(
                    vrp_layer,
                    specialties_name,
                    specialties_source,
                    "Name Name #;Description Description #",
                    "5000 Meters",
                    append="CLEAR"
                )

                arcpy.na.AddLocations(
                    vrp_layer,
                    routes_name,
                    vehicle_layer,
                    "Name Name #;Description Description #;StartDepotName StartDepotName #;EndDepotName EndDepotName #;StartDepotServiceTime StartDepotServiceTime #;EndDepotServiceTime EndDepotServiceTime #;EarliestStartTime EarliestStartTime '8:00:00 a. m.';LatestStartTime LatestStartTime '10:00:00 a. m.';ArriveDepartDelay ArriveDepartDelay #;Capacities Capacities #;FixedCost FixedCost #;CostPerUnitTime CostPerUnitTime 1;CostPerUnitDistance CostPerUnitDistance #;OvertimeStartTime OvertimeStartTime #;CostPerUnitOvertime CostPerUnitOvertime #;MaxOrderCount MaxOrderCount 30;MaxTotalTime MaxTotalTime #;MaxTotalTravelTime MaxTotalTravelTime #;MaxTotalDistance MaxTotalDistance #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 1",
                    "5000 Meters",
                    append="CLEAR"
                )

                arcpy.management.MakeFeatureLayer(orders_source, valid_orders_view, "OBJECTID IS NOT NULL")
                arcpy.na.AddLocations(
                    vrp_layer,
                    orders_name,
                    valid_orders_view,
                    "Name Name #;Description Description #;ServiceTime ServiceTime #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;MaxViolationTime1 MaxViolationTime1 #;MaxViolationTime2 MaxViolationTime2 #;DeliveryQuantities DeliveryQuantities #;PickupQuantities PickupQuantities #;Revenue Revenue #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 3;RouteName RouteName #;Sequence Sequence #;CurbApproach CurbApproach 0;InboundArriveTime InboundArriveTime #;OutboundDepartTime OutboundDepartTime #",
                    "5000 Meters",
                    sort_field="SpecialtyNames",
                    append="CLEAR",
                    snap_to_position_along_network="NO_SNAP",
                    exclude_restricted_elements="INCLUDE"
                )

                arcpy.na.AddLocations(
                    vrp_layer,
                    seeds_name,
                    vehicle_layer,
                    "RouteName Name #;SeedPointType # 1",
                    "5000 Meters",
                    append="CLEAR"
                )

                arcpy.management.MakeTableView(breaks_source, breaks_view, where_clause=f"RouteName = '{route_name}'")
                arcpy.na.AddLocations(
                    vrp_layer,
                    breaks_name,
                    breaks_view,
                    "RouteName RouteName #",
                    "5000 Meters",
                    append="CLEAR"
                )

                arcpy.na.AddLocations(
                    vrp_layer,
                    depots_name,
                    depots_source,
                    "Name Name #;Description Description #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;CurbApproach CurbApproach 0",
                    "5000 Meters",
                    append="CLEAR"
                )

                arcpy.management.MakeTableView(renewals_source, renewals_view, where_clause=f"RouteName = '{route_name}'")
                arcpy.na.AddLocations(
                    vrp_layer,
                    renewals_name,
                    renewals_view,
                    "RouteName RouteName #",
                    "5000 Meters",
                    append="CLEAR"
                )

                # ==========================================
                # 7. RESOLUCIÓN DEL MODELO VRP
                # ==========================================
                arcpy.na.Solve(
                    vrp_layer,
                    ignore_invalids="SKIP",
                    terminate_on_solve_error="CONTINUE",
                    simplification_tolerance="1 Meters"
                )

                # ==========================================
                # 8. EXTRACCIÓN Y CONSOLIDACIÓN DE RESULTADOS
                # ==========================================
                if arcpy.GetInstallInfo()['ProductName'] == 'Desktop':
                    orders_layer = arcpy.mapping.ListLayers(vrp_layer, orders_name)[0]
                    routes_layer = arcpy.mapping.ListLayers(vrp_layer, routes_name)[0]
                    depot_visits_layer = arcpy.mapping.ListLayers(vrp_layer, depot_visits_name)[0]
                    breaks_layer = arcpy.mapping.ListLayers(vrp_layer, breaks_name)[0]
                else:
                    orders_layer = vrp_layer.listLayers(orders_name)[0]
                    routes_layer = vrp_layer.listLayers(routes_name)[0]
                    depot_visits_layer = vrp_layer.listLayers(depot_visits_name)[0]
                    breaks_layer = vrp_layer.listLayers(breaks_name)[0]

                arcpy.management.Append(orders_layer, orders_result_source, "NO_TEST")
                arcpy.management.Append(routes_layer, vehicles_result_source, "NO_TEST")
                arcpy.management.Append(depot_visits_layer, depot_visits_result_source, "NO_TEST")
                arcpy.management.Append(breaks_layer, breaks_result_source, "NO_TEST")

                arcpy.management.MakeFeatureLayer(orders_layer, assigned_orders_layer, "RouteName IS NOT NULL")
                arcpy.management.MakeFeatureLayer(routes_layer, valid_routes_layer, "Name IS NOT NULL")
                arcpy.management.MakeFeatureLayer(orders_layer, orders_violation_layer, "ViolationTime1 > 0 OR ViolationTime2 > 0")

                arcpy.management.Append(assigned_orders_layer, orders_out, "NO_TEST")
                arcpy.management.Append(valid_routes_layer, routes_out, "NO_TEST")
                arcpy.management.Append(orders_violation_layer, orders_violation_out, "NO_TEST")
                arcpy.management.Append(depot_visits_layer, depots_visit_out, "NO_TEST")

                arcpy.management.Delete(vehicle_layer)
                arcpy.management.Delete(breaks_view)
                arcpy.management.Delete(renewals_view)
                arcpy.management.Delete(valid_orders_view)
                arcpy.management.Delete(vrp_layer)

            except Exception as e:
                arcpy.AddWarning(f"No fue posible completar el análisis para el vehículo {oid_value}: {str(e)}")
                arcpy.AddWarning(traceback.format_exc())
                continue

        arcpy.AddMessage("Análisis VRP GPF finalizado exitosamente.")
        return True

    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        return False
    except Exception as e:
        arcpy.AddError(f"Error de sistema inesperado: {str(e)}")
        arcpy.AddError(traceback.format_exc())
        return False


if __name__ == '__main__':
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"

    # --- Opción A: Rutas estáticas para pruebas locales (activa por defecto) ---
    p_orders_out = fr"{ruta_raiz}\Orders_Project_GPF"
    p_routes_out = fr"{ruta_raiz}\Routes_Project_GPF"
    p_orders_violation_out = fr"{ruta_raiz}\Orders_Violation_Project_GPF"
    p_depots_visit_out = fr"{ruta_raiz}\DepotVisits_Project_GPF"

    # --- Opción B: Parámetros desde Toolbox (descomentar al registrar como Script Tool) ---
    # p_orders_out = arcpy.GetParameterAsText(0)
    # p_routes_out = arcpy.GetParameterAsText(1)
    # p_orders_violation_out = arcpy.GetParameterAsText(2)
    # p_depots_visit_out = arcpy.GetParameterAsText(3)

    # --- Opción C: Parámetros por línea de comandos (descomentar para sys.argv) ---
    # p_orders_out = sys.argv[1]
    # p_routes_out = sys.argv[2]
    # p_orders_violation_out = sys.argv[3]
    # p_depots_visit_out = sys.argv[4]

    optimizar_rutas_gpf(p_orders_out, p_routes_out, p_orders_violation_out, p_depots_visit_out)
