# -*- coding: utf-8 -*-
import arcpy
import traceback

# Script para el ruteo VRP completo (GPF Truck Full Prod)
# Se migró desde ModelBuilder a Python para ArcGIS Pro y publicación posterior en ArcGIS Enterprise.

def optimizar_rutas_gpf(orders_out, routes_out, orders_violation_out, depots_visit_out):
    # Se habilita la sobreescritura de salidas para ejecuciones repetidas
    arcpy.env.overwriteOutput = True

    #RUTAS LOCALES PARA PRUEBAS
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"

    vehicles_bd = fr"{ruta_raiz}\VRP_VEHICLE"
    orders_db = fr"{ruta_raiz}\View_VRP_ORDERS"
    ecuador_nd = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Ecuador.gdb\Ecuador\Ecuador_ND"
    specialties_name_bd = fr"{ruta_raiz}\VRP_Specialtes_Name"
    breaks_bd = fr"{ruta_raiz}\VRP_BREAKS"
    depots_bd = fr"{ruta_raiz}\VRP_DEPOTS"
    routes_renewals_bd = fr"{ruta_raiz}\VRP_ROUTE_RENEWALS"

    # Tablas de resultado
    vrp_orders_result = fr"{ruta_raiz}\VRP_ORDERS_RESULT"
    vrp_vehicle_result = fr"{ruta_raiz}\VRP_VEHICLE_RESULT"
    vrp_breaks_result = fr"{ruta_raiz}\VRP_BREAKS_RESULT"
    vrp_depots_visits_result = fr"{ruta_raiz}\VRP_DEPOT_VISITS_RESULT"
    vrp_orders_violations_result = fr"{ruta_raiz}\VRP_ORDERS_VIOLATIONS"

    try:
        arcpy.AddMessage("Iniciando geoproceso VRP GPF Truck Full...")

        # ==========================================
        # 2. VALIDACIÓN INICIAL
        # ==========================================
        row_count = int(arcpy.management.GetCount(orders_db)[0])
        if row_count == 0:
            arcpy.AddWarning("No se encontraron órdenes para procesar.")
            return False

        # ==========================================
        # 3. ITERACIÓN DE VEHÍCULOS
        # ==========================================
        # En ModelBuilder el iterador corresponde a Iterate Feature Selection
        # sobre Vehicles BD agrupado por OBJECTID.
        oid_field = arcpy.Describe(vehicles_bd).OIDFieldName
        oid_values = []

        with arcpy.da.SearchCursor(vehicles_bd, [oid_field]) as cursor:
            for row in cursor:
                if row[0] is not None:
                    oid_values.append(row[0])

        if not oid_values:
            arcpy.AddWarning("No se encontraron vehículos disponibles para procesar.")
            return False

        arcpy.AddMessage(f"Se identificaron {len(oid_values)} vehículos para análisis.")

        for oid_value in oid_values:
            vehicle_layer = "Vehicle_Iter_Layer"
            breaks_view = "Breaks_View"
            renewals_view = "dbo_VRP_ROUTE_RENEWALS_View"
            orders_filter_valid = "OrdersDB_Filtered"
            orders_assigned_fl = "Orders_Layer"
            routes_valid_fl = "Routes_Layer"
            orders_violation_fl = "Orders_Violation_Valid"

            try:
                # Se genera la selección individual del vehículo actual
                where_vehicle = f"{arcpy.AddFieldDelimiters(vehicles_bd, oid_field)} = {oid_value}"
                arcpy.management.MakeFeatureLayer(vehicles_bd, vehicle_layer, where_vehicle)

                # Se obtiene el nombre de ruta/vehículo actual para filtros dependientes
                nombre_ruta = None
                with arcpy.da.SearchCursor(vehicle_layer, ["Name"]) as cursor_vehicle:
                    for row_vehicle in cursor_vehicle:
                        nombre_ruta = row_vehicle[0]
                        break

                if not nombre_ruta:
                    arcpy.AddWarning(f"No fue posible obtener el Name para el OBJECTID {oid_value}.")
                    arcpy.management.Delete(vehicle_layer)
                    continue

                arcpy.AddMessage(f"Procesando vehículo/ruta: {nombre_ruta}")

                # ==========================================
                # 4. CREACIÓN DE CAPA VRP
                # ==========================================
                vrp_layer_name = f"VRP_{nombre_ruta}"
                vrp_result = arcpy.na.MakeVehicleRoutingProblemLayer(
                    in_network_dataset=ecuador_nd,
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

                # Se identifican dinámicamente las subcapas del análisis
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
                # 5. CARGA DE LOCALIZACIONES
                # ==========================================
                arcpy.na.AddLocations(
                    in_network_analysis_layer=vrp_layer,
                    sub_layer=specialties_name,
                    in_table=specialties_name_bd,
                    field_mappings="Name Name #;Description Description #",
                    search_tolerance="5000 Meters",
                    append="CLEAR"
                )

                arcpy.na.AddLocations(
                    in_network_analysis_layer=vrp_layer,
                    sub_layer=routes_name,
                    in_table=vehicle_layer,
                    field_mappings="Name Name #;Description Description #;StartDepotName StartDepotName #;EndDepotName EndDepotName #;StartDepotServiceTime StartDepotServiceTime #;EndDepotServiceTime EndDepotServiceTime #;EarliestStartTime EarliestStartTime '8:00:00 a. m.';LatestStartTime LatestStartTime '10:00:00 a. m.';ArriveDepartDelay ArriveDepartDelay #;Capacities Capacities #;FixedCost FixedCost #;CostPerUnitTime CostPerUnitTime 1;CostPerUnitDistance CostPerUnitDistance #;OvertimeStartTime OvertimeStartTime #;CostPerUnitOvertime CostPerUnitOvertime #;MaxOrderCount MaxOrderCount 30;MaxTotalTime MaxTotalTime #;MaxTotalTravelTime MaxTotalTravelTime #;MaxTotalDistance MaxTotalDistance #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 1",
                    search_tolerance="5000 Meters",
                    append="CLEAR"
                )

                arcpy.management.MakeFeatureLayer(
                    in_features=orders_db,
                    out_layer=orders_filter_valid,
                    where_clause="OBJECTID IS NOT NULL"
                )

                arcpy.na.AddLocations(
                    in_network_analysis_layer=vrp_layer,
                    sub_layer=orders_name,
                    in_table=orders_filter_valid,
                    field_mappings="Name Name #;Description Description #;ServiceTime ServiceTime #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;MaxViolationTime1 MaxViolationTime1 #;MaxViolationTime2 MaxViolationTime2 #;DeliveryQuantities DeliveryQuantities #;PickupQuantities PickupQuantities #;Revenue Revenue #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 3;RouteName RouteName #;Sequence Sequence #;CurbApproach CurbApproach 0;InboundArriveTime InboundArriveTime #;OutboundDepartTime OutboundDepartTime #",
                    search_tolerance="5000 Meters",
                    sort_field="SpecialtyNames",
                    append="CLEAR",
                    snap_to_position_along_network="NO_SNAP",
                    exclude_restricted_elements="INCLUDE"
                )

                arcpy.na.AddLocations(
                    in_network_analysis_layer=vrp_layer,
                    sub_layer=seeds_name,
                    in_table=vehicle_layer,
                    field_mappings="RouteName Name #;SeedPointType # 1",
                    search_tolerance="5000 Meters",
                    append="CLEAR"
                )

                # El Add Join visual era Vehicle.Name -> Breaks_BD.RouteName
                # Para robustez en Python se reemplaza por una vista filtrada por la ruta actual.
                arcpy.management.MakeTableView(
                    in_table=breaks_bd,
                    out_view=breaks_view,
                    where_clause=f"RouteName = '{nombre_ruta}'"
                )

                arcpy.na.AddLocations(
                    in_network_analysis_layer=vrp_layer,
                    sub_layer=breaks_name,
                    in_table=breaks_view,
                    field_mappings="RouteName RouteName #",
                    search_tolerance="5000 Meters",
                    append="CLEAR"
                )

                arcpy.na.AddLocations(
                    in_network_analysis_layer=vrp_layer,
                    sub_layer=depots_name,
                    in_table=depots_bd,
                    field_mappings="Name Name #;Description Description #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;CurbApproach CurbApproach 0",
                    search_tolerance="5000 Meters",
                    append="CLEAR"
                )

                # En ModelBuilder el Make Table View usa: RouteName = '%NameVar%'
                arcpy.management.MakeTableView(
                    in_table=routes_renewals_bd,
                    out_view=renewals_view,
                    where_clause=f"RouteName = '{nombre_ruta}'"
                )

                arcpy.na.AddLocations(
                    in_network_analysis_layer=vrp_layer,
                    sub_layer=renewals_name,
                    in_table=renewals_view,
                    field_mappings="DepotName DepotName #;RouteName RouteName #;ServiceTime ServiceTime 40;Sequences # #",
                    search_tolerance="5000 Meters",
                    append="CLEAR"
                )

                # ==========================================
                # 6. SOLUCIÓN VRP
                # ==========================================
                arcpy.AddMessage(f"Ejecutando Solve para la ruta {nombre_ruta}...")
                arcpy.na.Solve(
                    in_network_analysis_layer=vrp_layer,
                    ignore_invalids="SKIP",
                    terminate_on_solve_error="CONTINUE",
                    simplification_tolerance="1 Meters"
                )

                # ==========================================
                # 7. EXTRACCIÓN DE SUBCAPAS
                # ==========================================
                if arcpy.GetInstallInfo()["ProductName"] == "Desktop":
                    orders_out_pre = arcpy.mapping.ListLayers(vrp_layer, orders_name)[0]
                    routes_out_pre = arcpy.mapping.ListLayers(vrp_layer, routes_name)[0]
                    breaks_out = arcpy.mapping.ListLayers(vrp_layer, breaks_name)[0]
                    depot_visits_out_pre = arcpy.mapping.ListLayers(vrp_layer, depot_visits_name)[0]
                else:
                    orders_out_pre = vrp_layer.listLayers(orders_name)[0]
                    routes_out_pre = vrp_layer.listLayers(routes_name)[0]
                    breaks_out = vrp_layer.listLayers(breaks_name)[0]
                    depot_visits_out_pre = vrp_layer.listLayers(depot_visits_name)[0]

                # ==========================================
                # 8. FILTROS Y APPEND DE RESULTADOS
                # ==========================================
                arcpy.management.MakeFeatureLayer(
                    in_features=orders_out_pre,
                    out_layer=orders_assigned_fl,
                    where_clause="\"RouteName\" IS NOT NULL"
                )
                arcpy.management.Append(
                    inputs=[orders_assigned_fl],
                    target=vrp_orders_result,
                    schema_type="NO_TEST"
                )

                arcpy.management.MakeFeatureLayer(
                    in_features=routes_out_pre,
                    out_layer=routes_valid_fl,
                    where_clause="\"OrderCount\" > 0"
                )
                arcpy.management.Append(
                    inputs=[routes_valid_fl],
                    target=vrp_vehicle_result,
                    schema_type="NO_TEST"
                )

                arcpy.management.Append(
                    inputs=[breaks_out],
                    target=vrp_breaks_result,
                    schema_type="NO_TEST"
                )

                arcpy.management.Append(
                    inputs=[depot_visits_out_pre],
                    target=vrp_depots_visits_result,
                    schema_type="NO_TEST"
                )

                arcpy.management.MakeFeatureLayer(
                    in_features=orders_out_pre,
                    out_layer=orders_violation_fl,
                    where_clause="Status IN (1,2,3,4) OR ViolatedConstraints IN (32)"
                )
                arcpy.management.Append(
                    inputs=[orders_violation_fl],
                    target=vrp_orders_violations_result,
                    schema_type="NO_TEST"
                )

                # ==========================================
                # 9. LIMPIEZA DE MEMORIA
                # ==========================================
                for temp_name in [
                    orders_filter_valid,
                    breaks_view,
                    renewals_view,
                    orders_assigned_fl,
                    routes_valid_fl,
                    orders_violation_fl,
                    vehicle_layer
                ]:
                    if arcpy.Exists(temp_name):
                        arcpy.management.Delete(temp_name)

                if arcpy.Exists(vrp_layer):
                    arcpy.management.Delete(vrp_layer)

            except arcpy.ExecuteError:
                arcpy.AddWarning(f"Fallo en el procesamiento de la ruta {oid_value}: {arcpy.GetMessages(2)}")
                for temp_name in [
                    orders_filter_valid,
                    breaks_view,
                    renewals_view,
                    orders_assigned_fl,
                    routes_valid_fl,
                    orders_violation_fl,
                    vehicle_layer
                ]:
                    if arcpy.Exists(temp_name):
                        arcpy.management.Delete(temp_name)
                continue

        # ==========================================
        # 10. SALIDAS FINALES DEL SCRIPT
        # ==========================================
        arcpy.management.MakeFeatureLayer(
            in_features=vrp_orders_result,
            out_layer=orders_out,
            where_clause="Name <> '0000000'"
        )

        arcpy.management.MakeFeatureLayer(
            in_features=vrp_vehicle_result,
            out_layer=routes_out,
            where_clause="Name <> '0000000'"
        )

        arcpy.management.MakeFeatureLayer(
            in_features=vrp_orders_violations_result,
            out_layer=orders_violation_out
        )

        arcpy.management.MakeFeatureLayer(
            in_features=vrp_depots_visits_result,
            out_layer=depots_visit_out
        )

        arcpy.AddMessage("Geoproceso finalizado exitosamente.")
        return True

    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        return False
    except Exception as e:
        arcpy.AddError(f"Error de sistema inesperado: {str(e)}")
        arcpy.AddError(traceback.format_exc())
        return False


if __name__ == '__main__':
    p_orders_out = arcpy.GetParameterAsText(0) if arcpy.GetParameterAsText(0) else "Orders_Out"
    p_routes_out = arcpy.GetParameterAsText(1) if arcpy.GetParameterAsText(1) else "Routes_Out"
    p_orders_violation_out = arcpy.GetParameterAsText(2) if arcpy.GetParameterAsText(2) else "Orders_Violation_Valid"
    p_depots_visit_out = arcpy.GetParameterAsText(3) if arcpy.GetParameterAsText(3) else "Depots_Visit_Out"

    optimizar_rutas_gpf(
        p_orders_out,
        p_routes_out,
        p_orders_violation_out,
        p_depots_visit_out
    )