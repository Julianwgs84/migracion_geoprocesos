# -*- coding: utf-8 -*-
import arcpy
import sys
import traceback


def obtener_factor_trafico(sde_workspace):
    factor_view   = fr"{sde_workspace}\norgasprod.dbo.View_FactorTraffic"
    factor_trafico = 2.0
    try:
        with arcpy.da.SearchCursor(factor_view, ["Factor"]) as cursor:
            for row in cursor:
                if row[0] is not None:
                    factor_trafico = float(row[0])
                break
    except Exception as e:
        arcpy.AddWarning(f"No se pudo leer FactorTraffic. Se utilizará el valor por defecto 2.0. Error: {e}")
    return factor_trafico


def encontrar_conductores_cercanos(order_id, travel_time_limit, driver_id_param, out_facilities_layer):
    arcpy.env.overwriteOutput = True

    # ==========================================
    # 1. RUTAS Y FUENTES DE DATOS
    # ==========================================

    # --- Opción A: Rutas estáticas para pruebas locales (activa por defecto) ---
    sde_workspace   = r"Database Connections\NorgasPROD.sde"
    order_source    = fr"{sde_workspace}\norgasprod.dbo.View_OrdersActiveForClosestFacilities"
    drivers_source  = fr"{sde_workspace}\norgasprod.dbo.View_DriversAvalaibleForClosestFacilities"
    colombia_streets_nd = r"C:\Users\Administrator\Desktop\IntelligisDocuments\NetworkDataset\Colombia.gdb\Colombia_Streets\Colombia_Streets_ND"

    # --- Opción B: Rutas desde Toolbox (descomentar al registrar como Script Tool) ---
    # sde_workspace       = arcpy.GetParameterAsText(4)
    # order_source        = arcpy.GetParameterAsText(5)
    # drivers_source      = arcpy.GetParameterAsText(6)
    # colombia_streets_nd = arcpy.GetParameterAsText(7)

    # --- Opción C: Rutas por argumentos de línea de comandos (descomentar para sys.argv) ---
    # sde_workspace       = sys.argv[5]
    # order_source        = sys.argv[6]
    # drivers_source      = sys.argv[7]
    # colombia_streets_nd = sys.argv[8]

    try:
        arcpy.AddMessage("Iniciando análisis Closest Facility con factor de tráfico...")

        # ==========================================
        # 2. VARIABLES Y FILTROS
        # ==========================================
        type_driver_id = 1

        if int(driver_id_param) == 0:
            filter_driver = "UserId <> 0"
        else:
            filter_driver = f"UserId = {driver_id_param}"

        driver_where_clause = f"TypeDriverId IN (1, {type_driver_id}) AND {filter_driver}"
        order_where_clause  = f"ItineraryDetailsId = {order_id}"

        factor_trafico = obtener_factor_trafico(sde_workspace)
        arcpy.AddMessage(f"Factor de tráfico aplicado: {factor_trafico}")

        # ==========================================
        # 3. PREPARACIÓN DE CAPAS
        # ==========================================
        arcpy.AddMessage("Generando capas de órdenes y conductores...")
        order_layer  = "Order_Filtered"
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
        # 4. CONFIGURACIÓN DE CAPA CLOSEST FACILITY
        # ==========================================
        arcpy.AddMessage("Configurando capa de análisis de red...")
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

        sub_layer_names = arcpy.na.GetNAClassNames(cf_layer)
        incidents_name  = sub_layer_names["Incidents"]
        facilities_name = sub_layer_names["Facilities"]
        routes_name     = sub_layer_names["CFRoutes"]

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

        # ==========================================
        # 5. RESOLUCIÓN DE RUTAS
        # ==========================================
        arcpy.AddMessage("Resolviendo rutas de menor tiempo...")
        arcpy.na.Solve(
            in_network_analysis_layer=cf_layer,
            ignore_invalids="SKIP",
            terminate_on_solve_error="CONTINUE",
            simplification_tolerance="1 Meters"
        )

        # ==========================================
        # 6. RESULTADOS Y AJUSTE POR TRÁFICO
        # ==========================================
        arcpy.AddMessage("Calculando tiempos ajustados por factor de tráfico...")
        if arcpy.GetInstallInfo()['ProductName'] == 'Desktop':
            routes_sublayer     = arcpy.mapping.ListLayers(cf_layer, routes_name)[0]
            facilities_sublayer = arcpy.mapping.ListLayers(cf_layer, facilities_name)[0]
        else:
            routes_sublayer     = cf_layer.listLayers(routes_name)[0]
            facilities_sublayer = cf_layer.listLayers(facilities_name)[0]

        expression_type = "PYTHON3" if arcpy.GetInstallInfo()['ProductName'] != 'Desktop' else "PYTHON_9.3"
        arcpy.management.CalculateField(
            in_table=routes_sublayer,
            field="Total_TravelTime",
            expression=f"!Total_TravelTime! * {factor_trafico}",
            expression_type=expression_type
        )

        arcpy.management.AddJoin(
            in_layer_or_view=facilities_sublayer,
            in_field="ObjectID",
            join_table=routes_sublayer,
            join_field="FacilityID"
        )

        final_where = f"({routes_name}.Total_TravelTime / {factor_trafico}) <= {travel_time_limit}"
        arcpy.management.MakeFeatureLayer(
            in_features=facilities_sublayer,
            out_layer=out_facilities_layer,
            where_clause=final_where
        )

        arcpy.AddMessage(f"Proceso Closest Facility finalizado. Conductores viables en: {out_facilities_layer}")
        return True

    except arcpy.ExecuteError:
        arcpy.AddError(arcpy.GetMessages(2))
        return False
    except Exception as e:
        arcpy.AddError(f"Error de sistema inesperado: {str(e)}")
        arcpy.AddError(traceback.format_exc())
        return False


if __name__ == '__main__':
    # --- Opción A: Valores estáticos para pruebas locales (activa por defecto) ---
    p_order_id         = "26611"
    p_travel_time      = "30"
    p_driver_id        = "0"
    p_out_layer        = "CF_Facilities"

    # --- Opción B: Parámetros desde Toolbox (descomentar al registrar como Script Tool) ---
    # p_order_id    = arcpy.GetParameterAsText(0)
    # p_travel_time = arcpy.GetParameterAsText(1)
    # p_driver_id   = arcpy.GetParameterAsText(2)
    # p_out_layer   = arcpy.GetParameterAsText(3)

    # --- Opción C: Parámetros por línea de comandos (descomentar para sys.argv) ---
    # p_order_id    = sys.argv[1]
    # p_travel_time = sys.argv[2]
    # p_driver_id   = sys.argv[3]
    # p_out_layer   = sys.argv[4]

    encontrar_conductores_cercanos(p_order_id, p_travel_time, p_driver_id, p_out_layer)
