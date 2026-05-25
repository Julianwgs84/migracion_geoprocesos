# -*- coding: utf-8 -*-
import arcpy
import traceback

# Script  para la optimización de rutas (Vehicle Routing Problem)

def optimizar_rutas_vrp(orders_out, routes_out, depot_visits_out):
    # Se habilita la sobreescritura de salidas para prevenir bloqueos de esquema
    arcpy.env.overwriteOutput = True
    
    # RUTAS LOCALES PARA PRUEBAS
    # Referencias temporales a geodatabase local para ejecución de prueba
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"
    
    # Inputs de la base de datos simulados localmente
    specialties_source = fr"{ruta_raiz}\VRP_Specialtes_Name"
    orders_source = fr"{ruta_raiz}\VRP_ORDERS_D1"
    depots_source = fr"{ruta_raiz}\VRP_DEPOTS"
    vehicles_source = fr"{ruta_raiz}\VRP_VEHICLE"
    
    # Network dataset local
    transit_nd = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Panama.gdb\TRANSIT\TRANSIT_ND"
    
    # Se define el sistema de coordenadas de salida WGS_1984 mediante código EPSG
    spatial_ref_wgs84 = arcpy.SpatialReference(4326)

    try:
        arcpy.AddMessage("Iniciando análisis Vehicle Routing Problem (VRP)...")
        
        # ==========================================
        # 2. CREACIÓN DE CAPA VRP
        # ==========================================
        # Se soluciona el fallo de exportación arcpy.ERROR_UNKNOWN_TOOLBOX de ModelBuilder
        vrp_layer_name = "VRP_Analysis_Layer"
        vrp_result = arcpy.na.MakeVehicleRoutingProblemLayer(
            in_network_dataset=transit_nd,
            out_network_analysis_layer=vrp_layer_name,
            time_impedance="Minutos",
            distance_impedance="",
            distance_units="Meters",
            time_window_factor="High",
            excess_transit_factor="Low",
            UTurn_policy="ALLOW_DEAD_ENDS_AND_INTERSECTIONS_ONLY"
        )
        vrp_layer = vrp_result[0]
        
        # Se extraen dinámicamente los nombres de las subcapas del grupo VRP
        sub_layer_names = arcpy.na.GetNAClassNames(vrp_layer)
        specialties_name = sub_layer_names["Specialties"]
        orders_name = sub_layer_names["Orders"]
        depots_name = sub_layer_names["Depots"]
        routes_name = sub_layer_names["Routes"]
        seeds_name = sub_layer_names["RouteSeedPoints"]
        depot_visits_name = sub_layer_names["DepotVisits"]

        # ==========================================
        # 3. CARGA DE LOCALIZACIONES
        # ==========================================
        arcpy.AddMessage("Integrando parámetros operativos de VRP (Especialidades, Órdenes, Depósitos, Vehículos)...")
        
        # Integración de Especialidades
        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=specialties_name,
            in_table=specialties_source,
            field_mappings="Name Name #;Description Description #",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )
        
        # Integración de Órdenes
        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=orders_name,
            in_table=orders_source,
            field_mappings="Name Name #;Description Description #;ServiceTime ServiceTime #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;MaxViolationTime1 MaxViolationTime1 #;MaxViolationTime2 MaxViolationTime2 #;DeliveryQuantities DeliveryQuantities #;PickupQuantities PickupQuantities #;Revenue Revenue #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 3;RouteName RouteName #;Sequence Sequence #;CurbApproach CurbApproach 0;InboundArriveTime InboundArriveTime #;OutboundDepartTime OutboundDepartTime #",
            search_tolerance="5000 Meters",
            append="CLEAR",
            snap_to_position_along_network="NO_SNAP"
        )
        
        # Integración de Depósitos
        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=depots_name,
            in_table=depots_source,
            field_mappings="Name Name #;Description Description #;TimeWindowStart1 TimeWindowStart1 #;TimeWindowEnd1 TimeWindowEnd1 #;TimeWindowStart2 TimeWindowStart2 #;TimeWindowEnd2 TimeWindowEnd2 #;CurbApproach CurbApproach 0",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )
        
        # Integración de Vehículos / Rutas
        arcpy.na.AddLocations(
            in_network_analysis_layer=vrp_layer,
            sub_layer=routes_name,
            in_table=vehicles_source,
            field_mappings="Name Name #;Description Description #;StartDepotName StartDepotName #;EndDepotName EndDepotName #;StartDepotServiceTime StartDepotServiceTime #;EndDepotServiceTime EndDepotServiceTime #;EarliestStartTime EarliestStartTime '8:00:00 a. m.';LatestStartTime LatestStartTime '10:00:00 a. m.';ArriveDepartDelay ArriveDepartDelay #;Capacities Capacities #;FixedCost FixedCost #;CostPerUnitTime CostPerUnitTime 1;CostPerUnitDistance CostPerUnitDistance #;OvertimeStartTime OvertimeStartTime #;CostPerUnitOvertime CostPerUnitOvertime #;MaxOrderCount MaxOrderCount 30;MaxTotalTime MaxTotalTime #;MaxTotalTravelTime MaxTotalTravelTime #;MaxTotalDistance MaxTotalDistance #;SpecialtyNames SpecialtyNames #;AssignmentRule AssignmentRule 1",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )
        
        # Integración de Puntos Semilla de Ruta
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
        arcpy.AddMessage("Ejecutando algoritmo de solución VRP. Este proceso requiere alto nivel de cómputo...")
        arcpy.na.Solve(
            in_network_analysis_layer=vrp_layer,
            ignore_invalids="SKIP",
            terminate_on_solve_error="CONTINUE",
            simplification_tolerance="1 Meters"
        )

        # ==========================================
        # 5. EXTRACCIÓN Y REPROYECCIÓN A WGS84
        # ==========================================
        arcpy.AddMessage("Extrayendo resultados de subcapas y aplicando proyección geográfica EPSG 4326...")
        
        # Extracción programática que reemplaza la herramienta fallida SelectData
        if arcpy.GetInstallInfo()['ProductName'] == 'Desktop':
            out_orders_layer = arcpy.mapping.ListLayers(vrp_layer, orders_name)[0]
            out_routes_layer = arcpy.mapping.ListLayers(vrp_layer, routes_name)[0]
            out_depot_visits_layer = arcpy.mapping.ListLayers(vrp_layer, depot_visits_name)[0]
        else: # Entorno ArcGIS Pro
            out_orders_layer = vrp_layer.listLayers(orders_name)[0]
            out_routes_layer = vrp_layer.listLayers(routes_name)[0]
            out_depot_visits_layer = vrp_layer.listLayers(depot_visits_name)[0]

        # Reproyección a sistema WGS84 para visualización web
        arcpy.management.Project(
            in_dataset=out_orders_layer,
            out_dataset=orders_out,
            out_coor_system=spatial_ref_wgs84
        )
        
        arcpy.management.Project(
            in_dataset=out_routes_layer,
            out_dataset=routes_out,
            out_coor_system=spatial_ref_wgs84
        )
        
        arcpy.management.Project(
            in_dataset=out_depot_visits_layer,
            out_dataset=depot_visits_out,
            out_coor_system=spatial_ref_wgs84
        )

        # Se elimina el entorno de análisis de red para garantizar la liberación de memoria en el servidor
        arcpy.management.Delete(vrp_layer)
        
        arcpy.AddMessage("Geoproceso VRP consolidado y proyecciones finalizadas exitosamente.")
        return True

    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        return False
    except Exception as e:
        arcpy.AddError(f"Error de sistema inesperado: {str(e)}")
        arcpy.AddError(traceback.format_exc())
        return False

if __name__ == '__main__':
    # Configuración de variables de salida que la herramienta de Toolbox pasará como parámetros
    p_orders_out = arcpy.GetParameterAsText(0) if arcpy.GetParameterAsText(0) else r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb\Orders_Project"
    p_routes_out = arcpy.GetParameterAsText(1) if arcpy.GetParameterAsText(1) else r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb\Routes_Project"
    p_depot_visits_out = arcpy.GetParameterAsText(2) if arcpy.GetParameterAsText(2) else r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb\DepotVisits_Project"
    
    optimizar_rutas_vrp(p_orders_out, p_routes_out, p_depot_visits_out)