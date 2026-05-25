# -*- coding: utf-8 -*-
import arcpy
import sys
import traceback


def debe_detener_proceso(row_count, condition_str):
    return row_count == 0 and condition_str.upper() == "FALSE"


def model_vrp_gpf_truck(
    vehicles_source,
    orders_source,
    network_dataset,
    specialties_source,
    breaks_source,
    depots_source,
    renewals_source,
    orders_result_source,
    vehicles_result_source,
    depot_visits_result_source,
    breaks_result_source,
    orders_output,
    routes_output,
    output_layer_name="Vehicle Routing Problem"
):
    arcpy.env.overwriteOutput = True
    arcpy.AddMessage("Iniciando análisis VRP...")

    row_count = int(arcpy.management.GetCount(in_rows=orders_source)[0])
    if debe_detener_proceso(row_count, "FALSE"):
        arcpy.AddWarning("No se encontraron órdenes para procesar. La ejecución finaliza sin resultados.")
        return

    vehicle_ids = []
    with arcpy.da.SearchCursor(vehicles_source, ["OBJECTID"]) as cursor:
        for row in cursor:
            vehicle_ids.append(row[0])

    for object_id in vehicle_ids:
        arcpy.AddMessage(f"Procesando vehículo OBJECTID: {object_id}")

        vehicle_layer = "Vehicle_Iter_Layer"
        breaks_view = "Breaks_Filtered"
        renewals_view = "Renewals_Filtered"
        orders_view = "Orders_Filtered"

        try:
            where_vehicle = f"OBJECTID = {object_id}"
            arcpy.management.MakeFeatureLayer(vehicles_source, vehicle_layer, where_vehicle)

            route_name = None
            specialty_names = None
            with arcpy.da.SearchCursor(vehicle_layer, ["SpecialtyNames", "Name"]) as cursor_vehicle:
                for row in cursor_vehicle:
                    specialty_names = row[0]
                    route_name = row[1]
                    break

            if not route_name:
                arcpy.AddWarning(f"No se encontró el nombre de ruta para el vehículo {object_id}.")
                arcpy.management.Delete(vehicle_layer)
                continue

            arcpy.AddMessage(f"Procesando vehículo/ruta: {route_name}")

            vrp_layer = arcpy.na.MakeVehicleRoutingProblemLayer(
                in_network_dataset=network_dataset,
                out_network_analysis_layer=output_layer_name,
                time_impedance="TravelTime",
                distance_impedance="Kilometers",
                distance_units="Meters",
                default_date="14/06/2000 9:33:49 p. m.",
                capacity_count=3,
                time_window_factor="High",
                excess_transit_factor="Low",
                UTurn_policy="ALLOW_DEAD_ENDS_AND_INTERSECTIONS_ONLY"
            )[0]

            na_classes = arcpy.na.GetNAClassNames(vrp_layer)
            specialties_layer = na_classes["Specialties"]
            routes_layer = na_classes["Routes"]
            orders_layer = na_classes["Orders"]
            seed_points_layer = na_classes["RouteSeedPoints"]
            breaks_layer = na_classes["Breaks"]
            depots_layer = na_classes["Depots"]
            renewals_layer = na_classes["RouteRenewals"]
            depot_visits_layer = na_classes["DepotVisits"]

            arcpy.na.AddLocations(vrp_layer, specialties_layer, specialties_source, "Name Name #;Description Description #", "5000 Meters", append="CLEAR")
            arcpy.na.AddLocations(vrp_layer, routes_layer, vehicle_layer, "Name Name #;Description Description #;StartDepotName StartDepotName #;EndDepotName EndDepotName #;StartDepotServiceTime StartDepotServiceTime #;EndDepotServiceTime EndDepotServiceTime #;EarliestStartTime EarliestStartTime '8:00:00 a. m.';LatestStartTime LatestStartTime '10:00:00 a. m.';ArriveDepartDelay ArriveDepartDelay #;Capacities Capacities #;FixedCost FixedCost #;CostPerUnitTime CostPerUnitTime 1;CostPerUnitDistance CostPerUnitDistance #;OvertimeStartTime OvertimeStartTime #;CostPerUnitOvertime CostPerUnitOvertime #;MaxOrderCount MaxOrderCount 30;MaxTotalTime MaxTotalTime #;MaxTotalTravelTime MaxTotalTravelTime #;MaxTotalDistance MaxTotalDistance #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 1", "5000 Meters", append="CLEAR")

            arcpy.management.MakeFeatureLayer(orders_source, orders_view, "OBJECTID IS NOT NULL")
            arcpy.na.AddLocations(vrp_layer, orders_layer, orders_view, "Name Name #;Description Description #;ServiceTime ServiceTime #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;MaxViolationTime1 MaxViolationTime1 #;MaxViolationTime2 MaxViolationTime2 #;DeliveryQuantities DeliveryQuantities #;PickupQuantities PickupQuantities #;Revenue Revenue #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 3;RouteName RouteName #;Sequence Sequence #;CurbApproach CurbApproach 0;InboundArriveTime InboundArriveTime #;OutboundDepartTime OutboundDepartTime #", "5000 Meters", sort_field="SpecialtyNames", append="CLEAR", snap_to_position_along_network="NO_SNAP", exclude_restricted_elements="INCLUDE")
            arcpy.na.AddLocations(vrp_layer, seed_points_layer, vehicle_layer, "RouteName Name #;SeedPointType # 1", "5000 Meters", append="CLEAR")

            arcpy.management.MakeTableView(breaks_source, breaks_view, f"RouteName = '{route_name}'")
            arcpy.na.AddLocations(vrp_layer, breaks_layer, breaks_view, "RouteName RouteName #", "5000 Meters", append="CLEAR")

            arcpy.na.AddLocations(vrp_layer, depots_layer, depots_source, "Name Name #;Description Description #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;CurbApproach CurbApproach 0", "5000 Meters", append="CLEAR")

            arcpy.management.MakeTableView(renewals_source, renewals_view, f"RouteName = '{route_name}'")
            arcpy.na.AddLocations(vrp_layer, renewals_layer, renewals_view, "RouteName RouteName #", "5000 Meters", append="CLEAR")

            arcpy.na.Solve(vrp_layer, ignore_invalids="SKIP", terminate_on_solve_error="CONTINUE", simplification_tolerance="1 Meters")

            if arcpy.GetInstallInfo()['ProductName'] == 'Desktop':
                vrp_orders_layer = arcpy.mapping.ListLayers(vrp_layer, orders_layer)[0]
                vrp_routes_layer = arcpy.mapping.ListLayers(vrp_layer, routes_layer)[0]
                vrp_breaks_layer = arcpy.mapping.ListLayers(vrp_layer, breaks_layer)[0]
                vrp_depot_visits_layer = arcpy.mapping.ListLayers(vrp_layer, depot_visits_layer)[0]
            else:
                vrp_orders_layer = vrp_layer.listLayers(orders_layer)[0]
                vrp_routes_layer = vrp_layer.listLayers(routes_layer)[0]
                vrp_breaks_layer = vrp_layer.listLayers(breaks_layer)[0]
                vrp_depot_visits_layer = vrp_layer.listLayers(depot_visits_layer)[0]

            arcpy.management.Append(vrp_orders_layer, orders_result_source, "NO_TEST")
            arcpy.management.Append(vrp_routes_layer, vehicles_result_source, "NO_TEST")
            arcpy.management.Append(vrp_depot_visits_layer, depot_visits_result_source, "NO_TEST")
            arcpy.management.Append(vrp_breaks_layer, breaks_result_source, "NO_TEST")

            assigned_orders_layer = "Assigned_Orders_Layer"
            valid_routes_layer = "Valid_Routes_Layer"
            arcpy.management.MakeFeatureLayer(vrp_orders_layer, assigned_orders_layer, "RouteName IS NOT NULL")
            arcpy.management.MakeFeatureLayer(vrp_routes_layer, valid_routes_layer, "Name IS NOT NULL")

            arcpy.management.Append(assigned_orders_layer, orders_output, "NO_TEST")
            arcpy.management.Append(valid_routes_layer, routes_output, "NO_TEST")

            arcpy.management.Delete(vrp_layer)
            arcpy.management.Delete(vehicle_layer)
            arcpy.management.Delete(breaks_view)
            arcpy.management.Delete(renewals_view)
            arcpy.management.Delete(orders_view)

        except arcpy.ExecuteError:
            arcpy.AddWarning(arcpy.GetMessages(2))
        except Exception as e:
            arcpy.AddWarning(f"No fue posible completar el análisis para el vehículo {object_id}: {str(e)}")
            arcpy.AddWarning(traceback.format_exc())


if __name__ == '__main__':
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"

    # --- Opción A: Rutas estáticas para pruebas locales (activa por defecto) ---
    p_vehicles_source = fr"{ruta_raiz}\VRP_VEHICLE"
    p_orders_source = fr"{ruta_raiz}\View_VRP_ORDERS"
    p_network_dataset = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Ecuador.gdb\Ecuador\Ecuador_ND"
    p_specialties_source = fr"{ruta_raiz}\VRP_Specialtes_Name"
    p_breaks_source = fr"{ruta_raiz}\VRP_BREAKS"
    p_depots_source = fr"{ruta_raiz}\VRP_DEPOTS"
    p_renewals_source = fr"{ruta_raiz}\VRP_ROUTE_RENEWALS"
    p_orders_result_source = fr"{ruta_raiz}\VRP_ORDERS_RESULT"
    p_vehicles_result_source = fr"{ruta_raiz}\VRP_VEHICLE_RESULT"
    p_depot_visits_result_source = fr"{ruta_raiz}\VRP_DEPOT_VISITS_RESULT"
    p_breaks_result_source = fr"{ruta_raiz}\VRP_BREAKS_RESULT"
    p_orders_output = fr"{ruta_raiz}\Orders_Project_GPF_DEV"
    p_routes_output = fr"{ruta_raiz}\Routes_Project_GPF_DEV"

    # --- Opción B: Parámetros desde Toolbox (descomentar al registrar como Script Tool) ---
    # p_vehicles_source = arcpy.GetParameterAsText(0)
    # p_orders_source = arcpy.GetParameterAsText(1)
    # p_network_dataset = arcpy.GetParameterAsText(2)
    # p_specialties_source = arcpy.GetParameterAsText(3)
    # p_breaks_source = arcpy.GetParameterAsText(4)
    # p_depots_source = arcpy.GetParameterAsText(5)
    # p_renewals_source = arcpy.GetParameterAsText(6)
    # p_orders_result_source = arcpy.GetParameterAsText(7)
    # p_vehicles_result_source = arcpy.GetParameterAsText(8)
    # p_depot_visits_result_source = arcpy.GetParameterAsText(9)
    # p_breaks_result_source = arcpy.GetParameterAsText(10)
    # p_orders_output = arcpy.GetParameterAsText(11)
    # p_routes_output = arcpy.GetParameterAsText(12)

    # --- Opción C: Parámetros por línea de comandos (descomentar para sys.argv) ---
    # p_vehicles_source = sys.argv[1]
    # p_orders_source = sys.argv[2]
    # p_network_dataset = sys.argv[3]
    # p_specialties_source = sys.argv[4]
    # p_breaks_source = sys.argv[5]
    # p_depots_source = sys.argv[6]
    # p_renewals_source = sys.argv[7]
    # p_orders_result_source = sys.argv[8]
    # p_vehicles_result_source = sys.argv[9]
    # p_depot_visits_result_source = sys.argv[10]
    # p_breaks_result_source = sys.argv[11]
    # p_orders_output = sys.argv[12]
    # p_routes_output = sys.argv[13]

    model_vrp_gpf_truck(
        p_vehicles_source,
        p_orders_source,
        p_network_dataset,
        p_specialties_source,
        p_breaks_source,
        p_depots_source,
        p_renewals_source,
        p_orders_result_source,
        p_vehicles_result_source,
        p_depot_visits_result_source,
        p_breaks_result_source,
        p_orders_output,
        p_routes_output
    )
