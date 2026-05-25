# -*- coding: utf-8 -*-
import arcpy
import traceback

# Script para Closest Facility con factor de tráfico,
# filtro por conductor, municipio y exclusión por cancelación previa.

def obtener_primer_valor(tabla, campo, where_clause=None):
    valor = None
    with arcpy.da.SearchCursor(tabla, [campo], where_clause=where_clause) as cursor:
        for row in cursor:
            valor = row[0]
            break
    return valor


def obtener_campos_orden(order_source, order_id):
    where_order = f"ItineraryDetailsId = {order_id}"
    fields = ["TypeDriverId", "MunicipalityId", "DriveTimeZ1", "DriveTimeZ2", "DriveTimeZ3"]
    with arcpy.da.SearchCursor(order_source, fields, where_clause=where_order) as cursor:
        for row in cursor:
            return {
                "TypeDriverId": row[0],
                "MunicipalityId": row[1],
                "DriveTimeZ1": row[2],
                "DriveTimeZ2": row[3],
                "DriveTimeZ3": row[4],
            }
    return None


def resolver_closest_facility(parameter_driver_id, parameter_order_id, parameter_travel_time, cf_facilities):
    # Se habilita la sobreescritura de salidas para pruebas repetidas.
    arcpy.env.overwriteOutput = True

    # ==========================================
    # 1. RUTAS LOCALES PARA PRUEBAS
    # ==========================================
    ruta_raiz = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\Geoprocesos_ArcGIS_Pro.gdb"

    factortraffic_bd = fr"{ruta_raiz}\View_FactorTraffic"
    order_source = fr"{ruta_raiz}\View_OrdersActiveForClosestFacilities"
    drivers_source = fr"{ruta_raiz}\View_DriversAvalaibleForClosestFacilities"
    colombia_streets_nd = r"D:\Geoprocesos\Geoprocesos_ArcGIS_Pro\NetworkDataset\Colombia.gdb\Colombia_Streets\Colombia_Streets_ND"

    try:
        arcpy.AddMessage("Iniciando análisis Closest Facility con factor de tráfico...")

        # ==========================================
        # 2. PARÁMETROS Y CONSULTAS BASE
        # ==========================================
        driver_id = int(parameter_driver_id)
        order_id = int(parameter_order_id)
        travel_time_option = int(parameter_travel_time)

        filter_driver = "UserId<>0" if driver_id == 0 else f"UserId={driver_id}"

        factor = obtener_primer_valor(factortraffic_bd, "Factor")
        if factor is None:
            factor = 1
            arcpy.AddWarning("No se encontró valor de factor de tráfico. Se utilizará 1 por defecto.")

        order_values = obtener_campos_orden(order_source, order_id)
        if not order_values:
            arcpy.AddWarning(f"No se encontró la orden con ItineraryDetailsId = {order_id}.")
            return False

        type_driver_id = order_values["TypeDriverId"]
        municipality_id = order_values["MunicipalityId"]
        drive_time_z1 = order_values["DriveTimeZ1"]
        drive_time_z2 = order_values["DriveTimeZ2"]
        drive_time_z3 = order_values["DriveTimeZ3"]

        filter_drive_time = drive_time_z1 if travel_time_option == 1 else drive_time_z2 if travel_time_option == 2 else drive_time_z3
        if filter_drive_time is None:
            arcpy.AddWarning("No se obtuvo un valor de DriveTime válido para la opción solicitada.")
            return False

        # ==========================================
        # 3. FILTRO DE ORDEN
        # ==========================================
        order_filtered = "Order_Filtered"
        arcpy.management.MakeFeatureLayer(
            in_features=order_source,
            out_layer=order_filtered,
            where_clause=f"ItineraryDetailsId={order_id}"
        )

        if int(arcpy.management.GetCount(order_filtered)[0]) == 0:
            arcpy.AddWarning("La capa de orden filtrada no contiene registros.")
            return False

        # ==========================================
        # 4. CREACIÓN DE CAPA CLOSEST FACILITY
        # ==========================================
        cf_layer_result = arcpy.na.MakeClosestFacilityLayer(
            in_network_dataset=colombia_streets_nd,
            out_network_analysis_layer="Closest_Facility_Prod",
            impedance_attribute="TravelTime",
            travel_from_to="TRAVEL_FROM",
            default_number_facilities_to_find=100,
            accumulate_attribute_name=["Kilometers", "TravelTime"]
        )
        cf_layer = cf_layer_result[0]

        sub_layer_names = arcpy.na.GetNAClassNames(cf_layer)
        incidents_name = sub_layer_names["Incidents"]
        facilities_name = sub_layer_names["Facilities"]
        routes_name = sub_layer_names["CFRoutes"]

        arcpy.na.AddLocations(
            in_network_analysis_layer=cf_layer,
            sub_layer=incidents_name,
            in_table=order_filtered,
            field_mappings="Name ItineraryDetailsId #;Cutoff_TravelTime Cutoff_TravelTime #",
            search_tolerance="5000 Meters",
            append="CLEAR"
        )

        # ==========================================
        # 5. FILTRO DE CONDUCTORES
        # ==========================================
        driver_filtered = "Driver_Filtered"
        where_driver = (
            f"TypeDriverId IN (1,{type_driver_id}) AND {filter_driver} "
            f"AND MunicipalityId={municipality_id} "
            f"AND (ItineraryCancelByDriver NOT LIKE '%{order_id}%' OR ItineraryCancelByDriver IS NULL)"
        )

        arcpy.management.MakeFeatureLayer(
            in_features=drivers_source,
            out_layer=driver_filtered,
            where_clause=where_driver
        )

        if int(arcpy.management.GetCount(driver_filtered)[0]) == 0:
            arcpy.AddWarning("No se encontraron conductores que cumplan los filtros definidos.")
            return False

        arcpy.na.AddLocations(
            in_network_analysis_layer=cf_layer,
            sub_layer=facilities_name,
            in_table=driver_filtered,
            field_mappings="Name UserID #;Attr_Kilometers # #",
            search_tolerance="5000 Meters",
            match_type="MATCH_TO_CLOSEST",
            append="CLEAR"
        )

        # ==========================================
        # 6. SOLVE
        # ==========================================
        arcpy.na.Solve(
            in_network_analysis_layer=cf_layer,
            ignore_invalids="SKIP",
            terminate_on_solve_error="CONTINUE",
            simplification_tolerance="1 Meters"
        )

        # ==========================================
        # 7. EXTRACCIÓN DE SUBCAPAS
        # ==========================================
        if arcpy.GetInstallInfo()["ProductName"] == "Desktop":
            routes_out = arcpy.mapping.ListLayers(cf_layer, routes_name)[0]
            facilities_out = arcpy.mapping.ListLayers(cf_layer, facilities_name)[0]
        else:
            routes_out = cf_layer.listLayers(routes_name)[0]
            facilities_out = cf_layer.listLayers(facilities_name)[0]

        # ==========================================
        # 8. APLICACIÓN DE FACTOR DE TRÁFICO
        # ==========================================
        expression_type = "PYTHON3" if arcpy.GetInstallInfo()["ProductName"] != "Desktop" else "PYTHON_9.3"
        arcpy.management.CalculateField(
            in_table=routes_out,
            field="Total_TravelTime",
            expression=f"!Total_TravelTime! * {factor}",
            expression_type=expression_type
        )

        facilities_join_routes = arcpy.management.AddJoin(
            in_layer_or_view=facilities_out,
            in_field="ObjectID",
            join_table=routes_out,
            join_field="FacilityID"
        )[0]

        final_where = f'("{routes_name}.Total_TravelTime" / {factor}) <= ({filter_drive_time})'
        arcpy.management.MakeFeatureLayer(
            in_features=facilities_join_routes,
            out_layer=cf_facilities,
            where_clause=final_where
        )

        arcpy.AddMessage("Geoproceso Closest Facility finalizado exitosamente.")
        return True

    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        return False
    except Exception as e:
        arcpy.AddError(f"Error de sistema inesperado: {str(e)}")
        arcpy.AddError(traceback.format_exc())
        return False


if __name__ == '__main__':
    p_driver_id = arcpy.GetParameterAsText(0) if arcpy.GetParameterAsText(0) else "0"
    p_order_id = arcpy.GetParameterAsText(1) if arcpy.GetParameterAsText(1) else "467131"
    p_travel_time = arcpy.GetParameterAsText(2) if arcpy.GetParameterAsText(2) else "1"
    p_cf_facilities = arcpy.GetParameterAsText(3) if arcpy.GetParameterAsText(3) else "CF_Facilities"

    resolver_closest_facility(
        p_driver_id,
        p_order_id,
        p_travel_time,
        p_cf_facilities
    )