# -*- coding: utf-8 -*-
"""
Migrated and Refactored 
Original Model: Model_CF_Norgas_QA_with_FactorTraffic

Description:
Finds the closest drivers to an order location based on travel time, 
applying a traffic factor to adjust the total travel time.
"""
import arcpy
import sys
import traceback

def get_traffic_factor(sde_workspace):
    """
    Replaces the 'GetFieldValue' utility from ModelBuilder.
    Reads the traffic factor from the View_FactorTraffic view.
    If the value is null or fails, defaults to 2.0 based on model configuration.
    """
    factor_view = fr"{sde_workspace}\norgasprod.dbo.View_FactorTraffic"
    traffic_factor = 2.0 # Default/Null fallback defined in the model (Null Value: 2.0)
    try:
        with arcpy.da.SearchCursor(factor_view, ["Factor"]) as cursor:
            for row in cursor:
                if row[0] is not None:
                    traffic_factor = float(row[0])
                break
    except Exception as e:
        arcpy.AddWarning(f"No se pudo leer FactorTraffic de la vista. Usando el valor por defecto 2.0. Error: {e}")
        
    return traffic_factor

def find_closest_drivers(order_id, travel_time_limit, driver_id_param, out_facilities_layer):
    """
    Calculates closest facilities (Drivers) to an Incident (Order) considering traffic.
    """
    arcpy.env.overwriteOutput = True
    
    # ==========================================
    # 1. PATHS (Update these parameters as needed)
    # ==========================================
    sde_workspace = r"Database Connections\NorgasPROD.sde"
    order_source = fr"{sde_workspace}\norgasprod.dbo.View_OrdersActiveForClosestFacilities"
    drivers_source = fr"{sde_workspace}\norgasprod.dbo.View_DriversAvalaibleForClosestFacilities"
    colombia_streets_nd = r"C:\Users\Administrator\Desktop\IntelligisDocuments\NetworkDataset\Colombia.gdb\Colombia_Streets\Colombia_Streets_ND"
    
    try:
        arcpy.AddMessage("Iniciando proceso de Closest Facility...")
        
        # ==========================================
        # 2. RESOLVE VARIABLES & FILTERS
        # ==========================================
        type_driver_id = 1 
        
        if int(driver_id_param) == 0:
            filter_driver = "UserId <> 0"
        else:
            filter_driver = f"UserId = {driver_id_param}"
            
        driver_where_clause = f"TypeDriverId IN (1, {type_driver_id}) AND {filter_driver}"
        order_where_clause = f"ItineraryDetailsId = {order_id}"
        
        # Obtenemos el factor de tráfico manejando el Null (2.0)
        traffic_factor = get_traffic_factor(sde_workspace)
        arcpy.AddMessage(f"Factor de tráfico aplicado: {traffic_factor}")

        # ==========================================
        # 3. PREPARE LAYERS
        # ==========================================
        arcpy.AddMessage("Creando Feature Layers de Órdenes y Conductores...")
        order_layer = "Order_Filtered"
        driver_layer = "Driver_Filtered"
        
        arcpy.management.MakeFeatureLayer(order_source, order_layer, order_where_clause)
        arcpy.management.MakeFeatureLayer(drivers_source, driver_layer, driver_where_clause)
        
        if int(arcpy.management.GetCount(order_layer)[0]) == 0:
            arcpy.AddWarning(f"No se encontraron órdenes activas con el ID {order_id}.")
            return
            
        if int(arcpy.management.GetCount(driver_layer)[0]) == 0:
            arcpy.AddWarning("No se encontraron conductores disponibles con los filtros aplicados.")
            return

        # ==========================================
        # 4. NETWORK ANALYSIS (CLOSEST FACILITY)
        # ==========================================
        arcpy.AddMessage("Configurando capa de Closest Facility...")
        
        cf_layer_name = "Closest_Facility_Layer"
        cf_result = arcpy.na.MakeClosestFacilityLayer(
            in_network_dataset=colombia_streets_nd,
            out_network_analysis_layer=cf_layer_name,
            impedance_attribute="TravelTime",
            travel_from_to="TRAVEL_FROM",
            default_number_facilities_to_find=100,
            accumulate_attribute_name=["Kilometers", "TravelTime"]
        )
        cf_layer = cf_result[0]
        
        # Extraer nombres de las subcapas
        sub_layer_names = arcpy.na.GetNAClassNames(cf_layer)
        incidents_name = sub_layer_names["Incidents"]
        facilities_name = sub_layer_names["Facilities"]
        routes_name = sub_layer_names["CFRoutes"]

        arcpy.na.AddLocations(
            in_network_analysis_layer=cf_layer,
            sub_layer=incidents_name,
            in_table=order_layer,
            field_mappings="Name ItineraryDetailsId #;Cutoff_TravelTime Cutoff_TravelTime #",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )
        
        arcpy.na.AddLocations(
            in_network_analysis_layer=cf_layer,
            sub_layer=facilities_name,
            in_table=driver_layer,
            field_mappings="Name UserID #;Attr_Kilometers # #",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )

        arcpy.AddMessage("Resolviendo rutas...")
        arcpy.na.Solve(
            in_network_analysis_layer=cf_layer,
            ignore_invalids="SKIP",
            terminate_on_solve_error="CONTINUE",
            simplification_tolerance="1 Meters"
        )

        # ==========================================
        # 5. EXTRACT RESULTS & CALCULATE TRAFFIC
        # ==========================================
        arcpy.AddMessage("Procesando resultados y sumando penalización de tráfico...")
        
        # En ArcPy, el equivalente a "Select Data" es listar y extraer las subcapas
        if arcpy.GetInstallInfo()['ProductName'] == 'Desktop':
            routes_sublayer = arcpy.mapping.ListLayers(cf_layer, routes_name)[0]
            facilities_sublayer = arcpy.mapping.ListLayers(cf_layer, facilities_name)[0]
        else: # ArcGIS Pro
            routes_sublayer = cf_layer.listLayers(routes_name)[0]
            facilities_sublayer = cf_layer.listLayers(facilities_name)[0]
        
        # Calcular nuevo TravelTime multiplicando por el factor de tráfico
        expression_type = "PYTHON3" if arcpy.GetInstallInfo()['ProductName'] != 'Desktop' else "PYTHON_9.3"
        arcpy.management.CalculateField(
            in_table=routes_sublayer,
            field="Total_TravelTime",
            expression=f"!Total_TravelTime! * {traffic_factor}",
            expression_type=expression_type
        )
        
        # Unir Rutas con Facilities
        arcpy.management.AddJoin(
            in_layer_or_view=facilities_sublayer,
            in_field="ObjectID",
            join_table=routes_sublayer,
            join_field="FacilityID"
        )
        
        # Aplicar el filtro final de tiempo máximo
        final_where = f"({routes_name}.Total_TravelTime / {traffic_factor}) <= {travel_time_limit}"
        arcpy.management.MakeFeatureLayer(
            in_features=facilities_sublayer,
            out_layer=out_facilities_layer,
            where_clause=final_where
        )
        
        arcpy.AddMessage(f"Proceso finalizado. Conductores viables exportados a: {out_facilities_layer}")
        return True

    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        return False
    except Exception as e:
        arcpy.AddError(f"Error inesperado: {str(e)}")
        arcpy.AddError(traceback.format_exc())
        return False

if __name__ == '__main__':
    # Configuración de parámetros para la herramienta Script de ArcMap/ArcGIS Pro
    param_order_id = arcpy.GetParameterAsText(0) if arcpy.GetParameterAsText(0) else "26611"
    param_travel_time = arcpy.GetParameterAsText(1) if arcpy.GetParameterAsText(1) else "30"
    param_driver_id = arcpy.GetParameterAsText(2) if arcpy.GetParameterAsText(2) else "0"
    out_layer = arcpy.GetParameterAsText(3) if arcpy.GetParameterAsText(3) else "CF_Facilities"
    
    find_closest_drivers(param_order_id, param_travel_time, param_driver_id, out_layer)