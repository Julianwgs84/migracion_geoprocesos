# -*- coding: utf-8 -*-
import arcpy
import sys

# Script  para el cálculo de rutas basado en trafico
# Se ajustaron las rutas a local para pruebas y se optimizó el código generado por ModelBuilder


def break_loop_condition(row_count, condition_str):
    """
    Función que replica el comportamiento de Stop en ModelBuilder.
    Devuelve True si se debe detener el ciclo (cuando row_count es 0).
    """
    # En el modelo original: if Row_Count == 0 and condition == "FALSE" -> Break
    if row_count == 0 and condition_str.upper() == "FALSE":
        return True
    return False

def model_vrp_gpf_truck(vehicles_db, orders_db, ecuador_nd, specialtes_name_db, breaks_db, depots_db, routes_renewals_db, vrp_orders_res, vrp_vehicle_res, vrp_depots_visits, vrp_breaks_res, vrp_orders_res_2, vrp_vehicle_res_2, output_layer_name="Vehicle Routing Problem"):
    
    # Permitir sobrescribir salidas
    arcpy.env.overwriteOutput = True
    arcpy.AddMessage("Iniciando análisis Vehicle Routing Problem (VRP)...")

    # 1. Comprobar si hay órdenes (Reemplazo del proceso Stop/Break loop)
    row_count = int(arcpy.management.GetCount(in_rows=orders_db)[0])
    if break_loop_condition(row_count, "FALSE"):
        arcpy.AddWarning("No se encontraron órdenes para procesar. Finalizando ejecución.")
        return

    # 2. REEMPLAZO DEL ITERADOR (Iterate Feature Selection)
    # Iterar sobre Vehicles_BD usando OBJECTID
    unique_vehicle_ids = []
    with arcpy.da.SearchCursor(vehicles_db, ["OBJECTID"]) as cursor:
        for row in cursor:
            # ModelBuilder muestra Skip Nulls desmarcado, así que agregamos todos
            unique_vehicle_ids.append(row[0])

    # 3. Ciclo principal por vehículo
    for obj_id in unique_vehicle_ids:
        arcpy.AddMessage(f"Procesando Vehículo OBJECTID: {obj_id}")
        
        vehicle_layer = "Vehicle_Iter_Layer"
        where_clause_veh = f"OBJECTID = {obj_id}"
        
        # Crear capa temporal para el vehículo iterado
        arcpy.management.MakeFeatureLayer(vehicles_db, vehicle_layer, where_clause_veh)

        # 4. REEMPLAZO DE GetFieldValue (Para SpecialtyNames y Name)
        specialty_names_var = None
        name_var = None
        with arcpy.da.SearchCursor(vehicle_layer, ["SpecialtyNames", "Name"]) as cursor:
            for row in cursor:
                specialty_names_var = str(row[0]) if row[0] is not None else ""
                name_var = str(row[1]) if row[1] is not None else ""
                break # Solo necesitamos el primer registro de la selección
        
        arcpy.AddMessage(f"  - Nombre: {name_var} | Especialidades: {specialty_names_var}")

        # Nombre de capa de red en memoria
        vrp_layer_name = f"{output_layer_name}_{obj_id}"
        
        try:
            # 5. Make Vehicle Routing Problem Layer (Corrección del ERROR_UNKNOWN_TOOLBOX)
            vrp_obj = arcpy.na.MakeVehicleRoutingProblemAnalysisLayer(
                in_network_dataset=ecuador_nd, 
                out_network_analysis_layer=vrp_layer_name, 
                time_impedance="TravelTime", 
                distance_impedance="Kilometers", 
                distance_units="Meters", 
                default_date="1/12/2019", # Puede pasarse a variable en el futuro
                capacity_count=3, 
                time_window_factor="High", 
                excess_transit_factor="Low", 
                UTurn_policy="ALLOW_DEAD_ENDS_AND_INTERSECTIONS_ONLY"
            )[0]

            # Add Locations: Specialties
            arcpy.na.AddLocations(vrp_obj, "Specialties", specialtes_name_db, "Name Name #;Description Description #", "5000 Meters", append="CLEAR")

            # Add Locations: Routes (Usando la capa del vehículo actual)
            arcpy.na.AddLocations(vrp_obj, "Routes", vehicle_layer, "Name Name #;Description Description #;StartDepotName StartDepotName #;EndDepotName EndDepotName #;StartDepotServiceTime StartDepotServiceTime #;EndDepotServiceTime EndDepotServiceTime #;EarliestStartTime EarliestStartTime '8:00:00 a. m.';LatestStartTime LatestStartTime '10:00:00 a. m.';ArriveDepartDelay ArriveDepartDelay #;Capacities Capacities #;FixedCost FixedCost #;CostPerUnitTime CostPerUnitTime 1;CostPerUnitDistance CostPerUnitDistance #;OvertimeStartTime OvertimeStartTime #;CostPerUnitOvertime CostPerUnitOvertime #;MaxOrderCount MaxOrderCount 30;MaxTotalTime MaxTotalTime #;MaxTotalTravelTime MaxTotalTravelTime #;MaxTotalDistance MaxTotalDistance #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 1", "5000 Meters", append="CLEAR")

            # Make Feature Layer: Orders
            orders_filter_valid = "OrdersDB_Filtered_Lyr"
            arcpy.management.MakeFeatureLayer(orders_db, orders_filter_valid, "OBJECTID IS NOT NULL")

            # Add Locations: Orders
            arcpy.na.AddLocations(vrp_obj, "Orders", orders_filter_valid, "Name Name #;Description Description #;ServiceTime ServiceTime #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;MaxViolationTime1 MaxViolationTime1 #;MaxViolationTime2 MaxViolationTime2 #;DeliveryQuantities DeliveryQuantities #;PickupQuantities PickupQuantities #;Revenue Revenue #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 3;RouteName RouteName #;Sequence Sequence #;CurbApproach CurbApproach 0;InboundArriveTime InboundArriveTime #;OutboundDepartTime OutboundDepartTime #", "5000 Meters", sort_field="SpecialtyNames", append="CLEAR", snap_to_position_along_network="NO_SNAP", exclude_restricted_elements="INCLUDE")

            # Add Locations: Seeds
            arcpy.na.AddLocations(vrp_obj, "Route Seed Points", vehicle_layer, "RouteName Name #;SeedPointType # 1", "5000 Meters", append="CLEAR")

            # Join para Breaks
            breaks_joined_layer = arcpy.management.AddJoin(vehicle_layer, "Name", breaks_db, "RouteName", "KEEP_COMMON")[0]

            # Add Locations: Breaks
            arcpy.na.AddLocations(vrp_obj, "Breaks", breaks_joined_layer, "RouteName # #", "5000 Meters", append="CLEAR")
            
            # Remover el Join una vez cargados los datos a NA (buena práctica en Python)
            arcpy.management.RemoveJoin(vehicle_layer)

            # Add Locations: Depots
            arcpy.na.AddLocations(vrp_obj, "Depots", depots_db, "Name Name #;Description Description #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;CurbApproach CurbApproach 0", "5000 Meters", append="CLEAR")

            # Route Renewals Filtrado usando la variable extraída (name_var)
            route_renewals_view = "VRP_ROUTE_RENEWALS_View"
            arcpy.management.MakeTableView(routes_renewals_db, route_renewals_view, f"RouteName='{name_var}'")

            # Add Locations: Route Renewals
            arcpy.na.AddLocations(vrp_obj, "Route Renewals", route_renewals_view, "DepotName DepotName #;RouteName RouteName #;ServiceTime ServiceTime 40;Sequences # #", "5000 Meters", append="CLEAR")

            # 6. SOLVE VRP
            arcpy.AddMessage("  - Resolviendo VRP...")
            arcpy.na.Solve(vrp_obj, ignore_invalids="SKIP", terminate_on_solve_error="CONTINUE", simplification_tolerance="1 Meters")

            # 7. REEMPLAZO DE SelectData: Extracción de Subcapas y Appends
            
            # 7.1 ORDERS
            sublayer_orders = f"{vrp_layer_name}\\Orders"
            orders_valid_lyr = "Orders_Valid_Lyr"
            arcpy.management.MakeFeatureLayer(sublayer_orders, orders_valid_lyr, "RouteName IS NOT NULL")
            arcpy.management.Append([orders_valid_lyr], vrp_orders_res, "TEST")
            
            orders_valid_3_lyr = "Orders_Layer_Def"
            arcpy.management.MakeFeatureLayer(sublayer_orders, orders_valid_3_lyr, "Name='000000000'")
            arcpy.management.Append([orders_valid_3_lyr], vrp_orders_res_2, "TEST")

            # 7.2 ROUTES
            sublayer_routes = f"{vrp_layer_name}\\Routes"
            routes_valid_lyr = "Routes_Valid_Lyr"
            arcpy.management.MakeFeatureLayer(sublayer_routes, routes_valid_lyr, "OrderCount > 0")
            arcpy.management.Append([routes_valid_lyr], vrp_vehicle_res, "TEST")
            
            routes_valid_2_lyr = "Routes_Layer_Def"
            arcpy.management.MakeFeatureLayer(sublayer_routes, routes_valid_2_lyr, "Name='0000000'")
            arcpy.management.Append([routes_valid_2_lyr], vrp_vehicle_res_2, "TEST")

            # 7.3 DEPOT VISITS
            sublayer_depots = f"{vrp_layer_name}\\Depot Visits" # Ojo al espacio
            arcpy.management.Append([sublayer_depots], vrp_depots_visits, "TEST")

            # 7.4 BREAKS
            sublayer_breaks = f"{vrp_layer_name}\\Breaks"
            arcpy.management.Append([sublayer_breaks], vrp_breaks_res, "TEST")

            arcpy.AddMessage(f"  - Vehículo {name_var} completado y datos anexados.")

        except Exception as e:
            arcpy.AddWarning(f"Error resolviendo el vehículo {name_var}: {str(e)}")
            
        finally:
            # Limpieza exhaustiva de memoria y bloqueos
            layers_to_delete = [vehicle_layer, orders_filter_valid, route_renewals_view, 
                                orders_valid_lyr, orders_valid_3_lyr, routes_valid_lyr, 
                                routes_valid_2_lyr, vrp_layer_name]
            for lyr in layers_to_delete:
                if arcpy.Exists(lyr):
                    arcpy.management.Delete(lyr)

    arcpy.AddMessage("Proceso VRP Finalizado Totalmente.")

if __name__ == '__main__':
    # =========================================================================
    # CONFIGURACIÓN DE RUTAS ESTÁTICAS (Actual)
    # =========================================================================
    vehicles_db = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_VEHICLE"
    orders_db = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.View_VRP_ORDERS"
    ecuador_nd = r"C:\Users\Administrator\Desktop\IntelligisDocuments\NetworkDataset\Ecuador.gdb\Ecuador\Ecuador_ND"
    specialtes_name_db = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_Specialtes_Name"
    breaks_db = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_BREAKS"
    depots_db = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_DEPOTS"
    routes_renewals_db = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_ROUTE_RENEWALS"
    
    # Salidas Result (Targets de Append)
    vrp_orders_res = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_ORDERS_RESULT"
    vrp_vehicle_res = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_VEHICLE_RESULT"
    vrp_depots_visits = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_DEPOT_VISITS_RESULT"
    vrp_breaks_res = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_BREAKS_RESULT"
    
    # Noté que en el código exportado usabas las mismas salidas para los segundos appends de Orders y Routes.
    vrp_orders_res_2 = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_ORDERS_RESULT"
    vrp_vehicle_res_2 = r"Database Connections\datasrvdesa.intelligisgroup.com_SmartMapsFT_GPF.sde\db_SmartMapsFT_GPF.dbo.VRP_VEHICLE_RESULT"

    model_vrp_gpf_truck(vehicles_db, orders_db, ecuador_nd, specialtes_name_db, breaks_db, depots_db, routes_renewals_db, vrp_orders_res, vrp_vehicle_res, vrp_depots_visits, vrp_breaks_res, vrp_orders_res_2, vrp_vehicle_res_2)

    # =========================================================================
    # CONFIGURACIÓN PARA TOOLBOX FUTURO (Comentado)
    # =========================================================================
    # vehicles_db = sys.argv[1]
    # orders_db = sys.argv[2]
    # ecuador_nd = sys.argv[3]
    # specialtes_name_db = sys.argv[4]
    # breaks_db = sys.argv[5]
    # depots_db = sys.argv[6]
    # routes_renewals_db = sys.argv[7]
    # vrp_orders_res = sys.argv[8]
    # vrp_vehicle_res = sys.argv[9]
    # vrp_depots_visits = sys.argv[10]
    # vrp_breaks_res = sys.argv[11]
    # vrp_orders_res_2 = sys.argv[12]
    # vrp_vehicle_res_2 = sys.argv[13]
    # model_vrp_gpf_truck(vehicles_db, orders_db, ecuador_nd, specialtes_name_db, breaks_db, depots_db, routes_renewals_db, vrp_orders_res, vrp_vehicle_res, vrp_depots_visits, vrp_breaks_res, vrp_orders_res_2, vrp_vehicle_res_2)
