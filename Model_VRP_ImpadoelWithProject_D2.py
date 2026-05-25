# -*- coding: utf-8 -*-
import arcpy
import sys
import traceback


def optimizar_rutas_vrp_d2(orders_out, routes_out, depot_visits_out):
    arcpy.env.overwriteOutput = True

    # ==========================================
    # 1. RUTAS Y FUENTES DE DATOS
    # ==========================================

    # --- Opción A: Rutas estáticas para pruebas locales (activa por defecto) ---
    ruta_raiz          = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"
    specialties_source = fr"{ruta_raiz}\VRP_Specialtes_Name"
    orders_source      = fr"{ruta_raiz}\VRP_ORDERS_D2"
    depots_source      = fr"{ruta_raiz}\VRP_DEPOTS"
    vehicles_source    = fr"{ruta_raiz}\VRP_VEHICLE"
    transit_nd         = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Panama.gdb\TRANSIT\TRANSIT_ND"

    # --- Opción B: Rutas desde Toolbox (descomentar al registrar como Script Tool) ---
    # specialties_source = arcpy.GetParameterAsText(3)
    # orders_source      = arcpy.GetParameterAsText(4)
    # depots_source      = arcpy.GetParameterAsText(5)
    # vehicles_source    = arcpy.GetParameterAsText(6)
    # transit_nd         = arcpy.GetParameterAsText(7)

    # --- Opción C: Rutas por argumentos de línea de comandos (descomentar para sys.argv) ---
    # specialties_source = sys.argv[4]
    # orders_source      = sys.argv[5]
    # depots_source      = sys.argv[6]
    # vehicles_source    = sys.argv[7]
    # transit_nd         = sys.argv[8]

    spatial_ref_wgs84 = arcpy.SpatialReference(4326)

    try:
        arcpy.AddMessage("Iniciando análisis VRP...")

        # ==========================================
        # 2. CONFIGURACIÓN DE CAPA VRP
        # ==========================================
        vrp_layer_name = "VRP_Analysis_Layer_D2"
        vrp_result = arcpy.na.MakeVehicleRoutingProblemLayer(
            in_network_dataset=transit_nd,
            out_network_analysis_layer=vrp_layer_name,
            time_impedance="Minutos",
            distance_impedance="Length",
            distance_units="Meters",
            time_window_factor="High",
            excess_transit_factor="Low",
            UTurn_policy="ALLOW_DEAD_ENDS_AND_INTERSECTIONS_ONLY"
        )
        vrp_layer = vrp_result[0]

        sub_layer_names   = arcpy.na.GetNAClassNames(vrp_layer)
        specialties_name  = sub_layer_names["Specialties"]
        orders_name       = sub_layer_names["Orders"]
        depots_name       = sub_layer_names["Depots"]
        routes_name       = sub_layer_names["Routes"]
        seeds_name        = sub_layer_names["RouteSeedPoints"]
        depot_visits_name = sub_layer_names["DepotVisits"]

        # ==========================================
        # 3. CARGA DE LOCALIZACIONES
        # ==========================================
        arcpy.AddMessage("Integrando parámetros operativos (Especialidades, Órdenes D2, Depósitos, Vehículos)...")

        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=specialties_name,
            in_table=specialties_source,
            field_mappings="Name Name #;Description Description #",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )

        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=orders_name,
            in_table=orders_source,
            field_mappings="Name Name #;Description Description #;ServiceTime ServiceTime #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;MaxViolationTime1 MaxViolationTime1 #;MaxViolationTime2 MaxViolationTime2 #;DeliveryQuantities DeliveryQuantities #;PickupQuantities PickupQuantities #;Revenue Revenue #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 3;RouteName RouteName #;Sequence Sequence #;CurbApproach CurbApproach 0;InboundArriveTime InboundArriveTime #;OutboundDepartTime OutboundDepartTime #",
            search_tolerance="5000 Meters",
            append="CLEAR",
            snap_to_position_along_network="NO_SNAP"
        )

        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=depots_name,
            in_table=depots_source,
            field_mappings="Name Name #;Description Description #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;CurbApproach CurbApproach 0",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )

        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=routes_name,
            in_table=vehicles_source,
            field_mappings="Name Name #;Description Description #;StartDepotName StartDepotName #;EndDepotName EndDepotName #;StartDepotServiceTime StartDepotServiceTime #;EndDepotServiceTime EndDepotServiceTime #;EarliestStartTime EarliestStartTime '8:00:00 a. m.';LatestStartTime LatestStartTime '10:00:00 a. m.';ArriveDepartDelay ArriveDepartDelay #;Capacities Capacities #;FixedCost FixedCost #;CostPerUnitTime CostPerUnitTime 1;CostPerUnitDistance CostPerUnitDistance #;OvertimeStartTime OvertimeStartTime #;CostPerUnitOvertime CostPerUnitOvertime #;MaxOrderCount MaxOrderCount 30;MaxTotalTime MaxTotalTime #;MaxTotalTravelTime MaxTotalTravelTime #;MaxTotalDistance MaxTotalDistance #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 1",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )

        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=seeds_name,
            in_table=vehicles_source,
            field_mappings="RouteName Name #;SeedPointType # 1",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )

        # ==========================================
        # 4. RESOLUCIÓN DEL MODELO VRP
        # ==========================================
        arcpy.AddMessage("Ejecutando algoritmo de enrutamiento VRP...")
        arcpy.na.Solve(
            in_network_analysis_layer=vrp_layer,
            ignore_invalids="SKIP",
            terminate_on_solve_error="CONTINUE",
            simplification_tolerance="1 Meters"
        )

        # ==========================================
        # 5. EXTRACCIÓN Y REPROYECCIÓN A WGS84
        # ==========================================
        arcpy.AddMessage("Extrayendo resultados y aplicando proyección geográfica (EPSG:4326)...")

        if arcpy.GetInstallInfo()['ProductName'] == 'Desktop':
            out_orders_layer      = arcpy.mapping.ListLayers(vrp_layer, orders_name)[0]
            out_routes_layer      = arcpy.mapping.ListLayers(vrp_layer, routes_name)[0]
            out_depot_visits_layer = arcpy.mapping.ListLayers(vrp_layer, depot_visits_name)[0]
        else:
            out_orders_layer      = vrp_layer.listLayers(orders_name)[0]
            out_routes_layer      = vrp_layer.listLayers(routes_name)[0]
            out_depot_visits_layer = vrp_layer.listLayers(depot_visits_name)[0]

        arcpy.management.Project(out_orders_layer,      orders_out,      spatial_ref_wgs84)
        arcpy.management.Project(out_routes_layer,      routes_out,      spatial_ref_wgs84)
        arcpy.management.Project(out_depot_visits_layer, depot_visits_out, spatial_ref_wgs84)

        arcpy.management.Delete(vrp_layer)

        arcpy.AddMessage("Proceso VRP finalizado exitosamente.")
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
    p_orders_out      = fr"{ruta_raiz}\Orders_Project_D2"
    p_routes_out      = fr"{ruta_raiz}\Routes_Project_D2"
    p_depot_visits_out = fr"{ruta_raiz}\DepotVisits_Project_D2"

    # --- Opción B: Parámetros desde Toolbox (descomentar al registrar como Script Tool) ---
    # p_orders_out      = arcpy.GetParameterAsText(0)
    # p_routes_out      = arcpy.GetParameterAsText(1)
    # p_depot_visits_out = arcpy.GetParameterAsText(2)

    # --- Opción C: Parámetros por línea de comandos (descomentar para sys.argv) ---
    # p_orders_out      = sys.argv[1]
    # p_routes_out      = sys.argv[2]
    # p_depot_visits_out = sys.argv[3]

    optimizar_rutas_vrp_d2(p_orders_out, p_routes_out, p_depot_visits_out)
