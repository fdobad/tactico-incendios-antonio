# input usuario
from auxiliary import get_data, create_forest
from simulator import generate_forest, generate, write, print_manejos_possibles, read_toml
from tactico import generate_random_walk_prices, model_t
from post_optimization import (
    biomass_with_fire_breacks,
    filtro,
    multiplicar_listas,
    sumar_por_solucion,
    graficar_vt_por_solucion,
    grafico_ahora_si,
    prop_quemada,
    biom_quemada,
)
from use_of_QGIS import fuels_creation, burn_prob_sol

# Bajar del gorwth simulator.py, auxiliary.py y tabla.csv

config = read_toml("config.toml")  # se lee el archivo de configuracion
config_opti = read_toml("config_opti.toml")  # se lee el archivo de configuracion de optimizacion

# si no han simulado los rodales para los cortafuegos
gdf = get_data(".\\test\\data_modificada\\proto_mod.shp")  # se adquiere el shapefile de los rodales

create_forest(gdf, "rid")  # se crea el bosque
RR = generate_forest()  # se generan los rodales
rodales = generate(rodales=RR)  # se generan los rodales con manejos


# si ya tienes cortafuegos y los rodales simulados
gdf_cf = get_data(
    ".\\cortafuegos\\data_cortafuegos\\data_modificada\\proto_mod.shp"
)  # se adquiere el shapefile rodales con cortafuegos
gdf = gdf.sort_values(by="rid")
gdf_cf = gdf_cf.sort_values(by="rid")

# se renombra la columna _mean a prop_cf (proporcion de cortafuegos) mean porque venia de estadistica zonal
gdf_cf.rename(columns={"_mean": "prop_cf"}, inplace=True)
rodales_cf = biomass_with_fire_breacks(
    rodales, gdf_cf, "rid"
)  # se generan los rodales con cortafuegos y manejos (se multiplica la biomasa por la proporcion sin cortafuegos)

# rodales = generate(config=read_toml(), models=get_models(), rodales=generate_random_forest())
write(rodales)
# lista con los años en los que se puede ralear y cosechar alguno de los rodales simulados
politicas = print_manejos_possibles(config)
prices = generate_random_walk_prices(
    config_opti["opti"]["Price"], config["horizonte"], mu=0.05, sigma=0.1
)  # genera precios aleatorios

# optimiza el modelo sin incendios ni cortafuegos y crea un csv con las soluciones
valores_objetivo, soluciones = model_t(rodales, politicas, prices, "rodales_sin_cortafuegos")
# optimiza el modelo sinn incendios pero con cortafuegos y crea un csv con las soluciones

valores_objetivo_cf, soluciones_cf = model_t(rodales_cf, politicas, prices, "rodales_con_cortafuegos")

# filtra los datos de los rodales dependiendo de las soluciones (ojo que las soluciones tienen que tener el mismo orden que los rodales)
filter = filtro(rodales, "soluciones_rodales_sin_cortafuegos.csv")  # f[soluciones][rodales]
filtro_cf = filtro(rodales_cf, "soluciones_rodales_con_cortafuegos.csv")

fuels_creation(gdf, filter, "./soluciones/data_modificada", "rid")  # crea los archivos de combustibles
fuels_creation(gdf_cf, filtro_cf, "./cortafuegos/soluciones/data_modificada", "rid")
# crea los archivos de combustibles con cortafuegos
bp_sin_cortafuegos = burn_prob_sol(
    config_opti["opti"]["soluciones"],
    ".tif",
    filter,
    "./soluciones/data_modificada",
    corta_fuegos=False,
    id="rid",
    paisaje="./test/data_modificada/proto_mod.shp",
)  # calcula la probabilidad de incendio sin cortafuegos
bp_con_cortafuegos = burn_prob_sol(
    config_opti["opti"]["soluciones"],
    ".tif",
    filtro_cf,
    "./cortafuegos/soluciones/data_modificada",
    corta_fuegos=True,
    id="rid",
    paisaje="./test/data_modificada/proto_mod.shp",
)  # calcula la probabilidad de incendio con cortafuegos
# biomasa vendida post incendios sin cortafuegos
new_biomass = multiplicar_listas(bp_sin_cortafuegos, filter)  # multiplica la biomasa por la probabilidad de incendio
# biomasa vendida post incendios con cortafuegos
new_biomass_con_cortafuegos = multiplicar_listas(
    bp_con_cortafuegos, filtro_cf
)  # multiplica la biomasa por la probabilidad de incendio con cortafuegos
##se actualizan los resultados post incendios, viendo las nuevas ganancias
biomass_for_solution, vt_sin_cortafuegos = sumar_por_solucion(new_biomass, prices)  # suma la biomasa por solucion
biomass_for_solution_con_cortafuegos, vt_con_cortafuegos = sumar_por_solucion(
    new_biomass_con_cortafuegos, prices
)  # suma la biomasa por solucion con cortafuegos
graficar_vt_por_solucion(
    vt_sin_cortafuegos, "sin_cortafuegos"
)  # grafica los valores objetivos por solucion sin cortafuegos
graficar_vt_por_solucion(
    vt_con_cortafuegos, "con_conrtafuegos"
)  # grafica los valores objetivos por solucion con cortafuegos
prop_quemada_vendible, prop_quemada_biomass, prop_quemada_vendible_cf, prop_quemada_biomass_cf = prop_quemada(
    filter, filtro_cf, bp_sin_cortafuegos, bp_con_cortafuegos, "Sin y con cortafuegos"
)
biomasa_quemada, vendible_quemada, biomasa_quemada_cf, vendible_quemada_cf = biom_quemada(
    filter, filtro_cf, bp_sin_cortafuegos, bp_con_cortafuegos, "Sin y con cortafuegos"
)

print("las ganancias por solucion post simulación de incendios son:")
print(biomass_for_solution)
# simulas los incendios"""
print("las ganancias por solucion post simulación de incendios son (con conrtafuegos):")
print(biomass_for_solution_con_cortafuegos)

# Encontrar el mejor valor y su índice en ambas listas
max_sin_cortafuegos = max(biomass_for_solution)
max_con_cortafuegos = max(biomass_for_solution_con_cortafuegos)

indice_sin_cortafuegos = biomass_for_solution.index(max_sin_cortafuegos)
indice_con_cortafuegos = biomass_for_solution_con_cortafuegos.index(max_con_cortafuegos)

if max_sin_cortafuegos > max_con_cortafuegos:
    mejor_valor = max_sin_cortafuegos
    origen = "sin cortafuegos"
    indice = indice_sin_cortafuegos
else:
    mejor_valor = max_con_cortafuegos
    origen = "con cortafuegos"
    indice = indice_con_cortafuegos

print(f"La mejor solución es la solucion {indice+1} {origen}, y su valor es {mejor_valor}.")

for i in range(5):
    print(biomass_for_solution_con_cortafuegos[i] / valores_objetivo_cf[i])
print("sin cortafuegos")
for i in range(5):
    print(biomass_for_solution[i] / valores_objetivo[i])


import ast  # cambiar por pickle


def read_bp_file(filepath):
    with open(filepath, "r") as file:
        content = file.read()

    # Convert the string representation of the list back to a Python list
    bp = ast.literal_eval(content)

    return bp


# Example usage
bp_sin_cortafuegos = read_bp_file("bp_sin_cortafuegos.txt")

# Verifying the structure
print(len(bp_sin_cortafuegos))  # Should print 5 (number of solutions)
print(len(bp_sin_cortafuegos[0]))  # Should print 60 (number of rodales)
print(len(bp_sin_cortafuegos[0][0]))  # Should print 10 (number of periods)


bp_con_cortafuegos = read_bp_file("bp_con_cortafuegos.txt")
# Verifying the structure
print(len(bp_con_cortafuegos))  # Should print 5 (number of solutions)
print(len(bp_con_cortafuegos[0]))  # Should print 60 (number of rodales)
print(len(bp_con_cortafuegos[0][0]))  # Should print 10 (number of periods)


import geopandas as gpd
import numpy as np

# Aquí asumo que tu GeoDataFrame se llama gdf
# Primer paso: crear la columna "ano" con ceros
gdf["ano"] = 0

# Segundo paso: crear la columna "event" con la condición "rodal" si "id" no es NaN
gdf["event"] = np.where(gdf["id"].notna(), "rodal", None)

# Tercer paso: añadir una columna vacía
gdf["burn_prob"] = None

# Cuarto paso: duplicar el GeoDataFrame y actualizar "ano"
duplicados = [gdf.copy() for _ in range(10)]
for i, dup in enumerate(duplicados):
    dup["ano"] = i

# Combina todos los duplicados en uno solo
gdf_final = gpd.GeoDataFrame(pd.concat(duplicados, ignore_index=True))

gdf_final


for r in range(len(filtro_cf[0])):
    for t in range(len(filtro_cf[0][0]["vendible"])):
        gdf_final.loc[(gdf_final["rid"] == filtro_cf[1][r]["rid"]) & (gdf_final["ano"] == t), "event"] = filtro_cf[1][
            r
        ]["eventos"][t]
        gdf_final.loc[(gdf_final["rid"] == filtro_cf[1][r]["rid"]) & (gdf_final["ano"] == t), "burn_prob"] = (
            bp_con_cortafuegos[1][r][t]
        )
gdf_final.to_file("C:\Local\Tesis\datos_grafico_gif_QGIS\cf\datos_grafico_gif_QGIS.shp")


import numpy as np

# Aquí asumo que tu GeoDataFrame se llama gdf
# Primer paso: crear la columna "ano" con ceros
gdf["ano"] = 0

# Segundo paso: crear la columna "event" con la condición "rodal" si "id" no es NaN
gdf["event"] = np.where(gdf["id"].notna(), "rodal", None)

# Tercer paso: añadir una columna vacía
gdf["burn_prob"] = None

# Cuarto paso: duplicar el GeoDataFrame y actualizar "ano"
duplicados = [gdf.copy() for _ in range(10)]
for i, dup in enumerate(duplicados):
    dup["ano"] = i

# Combina todos los duplicados en uno solo
gdf_final = gpd.GeoDataFrame(pd.concat(duplicados, ignore_index=True))

gdf_final


for r in range(len(filter[0])):
    for t in range(len(filter[0][0]["vendible"])):
        gdf_final.loc[(gdf_final["rid"] == filter[0][r]["rid"]) & (gdf_final["ano"] == t), "event"] = filter[0][r][
            "eventos"
        ][t]
        gdf_final.loc[(gdf_final["rid"] == filter[0][r]["rid"]) & (gdf_final["ano"] == t), "burn_prob"] = (
            bp_sin_cortafuegos[0][r][t]
        )
gdf_final.to_file("C:\Local\Tesis\datos_grafico_gif_QGIS\scf\datos_grafico_gif_QGIS_sin_cf.shp")
