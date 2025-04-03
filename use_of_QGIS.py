#!python3
"""
1. Enables a python script to run the QGIS environment,
without launching the QGIS GUI.
2. Enables a user located processing plugin to be loaded

Programmers must:
1. Adjust the path to the QGIS installation
(on windows also adjust qgis versions)

2. load the QGIS python environment to run

Helpful commands:
call "%USERPROFILE%\source\pyenv\python-qgis-cmd.bat"
%autoindent
ipython

References:
https://fire2a.github.io/docs/docs/qgis/README.html
https://gis.stackexchange.com/a/408738
https://gis.stackexchange.com/a/172849
"""
import sys
from platform import system as platform_system
from shutil import which
from os import pathsep, environ

from qgis.core import QgsApplication, QgsRasterLayer
import numpy as np
import tempfile
from pathlib import Path


if sys.version_info >= (3, 11):
    import tomllib

    with open("config.toml", "rb") as f:
        config = tomllib.load(f)
else:
    import toml

    config = toml.load("config.toml")

if sys.version_info >= (3, 11):
    import tomllib

    with open("config_opti.toml", "rb") as f:
        config_opti = tomllib.load(f)
else:
    import toml

    config_opti = toml.load("config_opti.toml")

#
## PART 1
#
if platform_system() == "Windows":
    QgsApplication.setPrefixPath("C:\\PROGRA~1\\QGIS33~1.2", True)
else:
    QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], False)
qgs.initQgis()

# Append the path where processing plugin can be found
if platform_system() == "Windows":
    sys.path.append("C:\\PROGRA~1\\QGIS33~1.2\\apps\\qgis\\python\\plugins")
else:
    sys.path.append("/usr/share/qgis/python/plugins")

import processing
from processing.core.Processing import Processing

Processing.initialize()

if platform_system() == "Windows":
    sys.path.append("C:\\Users\\xunxo\\AppData\\Roaming\\QGIS\\QGIS3\\profiles\\default\\python\\plugins")
else:
    sys.path.append("/home/fdo/.local/share/QGIS/QGIS3/profiles/default/python/plugins/")
# Add the algorithm provider
from fireanalyticstoolbox.fireanalyticstoolbox_provider import FireToolboxProvider

provider = FireToolboxProvider()
QgsApplication.processingRegistry().addProvider(provider)

print(processing.algorithmHelp("gdal:rasterize"))


def fuels_tif(temp_path, category, output):
    """Crea Raster de combustibles a partir de un shapefile y una columna de categoria."""
    fuels = processing.run(
        "gdal:rasterize",
        {
            "BURN": 0,
            "DATA_TYPE": 4,
            "EXTENT": "635415.270700000,638547.761600000,5835896.684200000,5838559.301400000 [EPSG:32718]",
            "EXTRA": "",
            "FIELD": category,
            "HEIGHT": 30,
            "INIT": None,
            "INPUT": str(temp_path),
            "INVERT": False,
            "NODATA": -9999,
            "OPTIONS": "",
            "OUTPUT": str(output),
            "UNITS": 1,
            "USE_Z": False,
            "WIDTH": 30,
        },
    )


from concurrent.futures import ThreadPoolExecutor
import tempfile
from pathlib import Path


def burn_prob(apath, temp_dir, fire_breaks=None, paisaje=".\\test\\data_base\\proto.shp"):
    """
    Simulate burn probability using the specified fuel raster and optional fire breaks.

    Args:
        apath (str): Path to the fuel raster file.
        temp_dir (str): Path to the temporary directory for storing intermediate files.
        fire_breacks (str, optional): Path to the fire breaks raster file. Defaults to None.

    Returns:
        DataFrame: DataFrame containing burn probabilities for each rodal.
    """
    # Crear una nueva ruta para el archivo .shp en el directorio temporal
    temp_output_path = Path(temp_dir) / "mean_bp.shp"
    result = processing.run(
        "fire2a:cell2firesimulator",
        {
            "CbdRaster": None,
            "CbhRaster": None,
            "CcfRaster": None,
            "DryRun": False,
            "ElevationRaster": None,
            "EnableCrownFire": False,
            "FireBreaksRaster": fire_breaks,
            "FoliarMoistureContent": 66,
            "FuelModel": 1,
            "FuelRaster": apath,
            "IgnitionMode": 0,
            "IgnitionPointVectorLayer": None,
            "IgnitionProbabilityMap": None,
            "IgnitionRadius": 0,
            "InstanceDirectory": "TEMPORARY_OUTPUT",
            "InstanceInProject": False,
            "LiveAndDeadFuelMoistureContentScenario": 2,
            "NumberOfSimulations": 50,
            "OtherCliArgs": "",
            "OutputOptions": [1, 2, 3, 4],
            "RandomNumberGeneratorSeed": 123,
            "ResultsDirectory": "TEMPORARY_OUTPUT",
            "ResultsInInstance": True,
            "SetFuelLayerStyle": False,
            "SimulationThreads": 15,
            "WeatherDirectory": "",
            "WeatherFile": ".\\example\\Weather.csv",
            "WeatherMode": 0,
        },
    )
    if rd := result.get("ResultsDirectory"):
        pass
    else:
        print("eerrrrr")

    bundle = processing.run(
        "fire2a:simulationresultsprocessing",
        {
            "BaseLayer": apath,
            "EnablePropagationDiGraph": True,
            "EnablePropagationScars": False,
            "OutputDirectory": "TEMPORARY_OUTPUT",
            "ResultsDirectory": result["ResultsDirectory"],
        },
    )

    raster_bp = processing.run(
        "native:zonalstatisticsfb",
        {
            "COLUMN_PREFIX": "_",
            "INPUT": paisaje,
            "INPUT_RASTER": bundle["BurnProbability"],
            "OUTPUT": str(temp_output_path),
            "RASTER_BAND": 1,
            "STATISTICS": [2, 6],
        },
    )
    from auxiliary import get_data

    burn_prob = get_data(str(raster_bp["OUTPUT"]))
    burn_prob = burn_prob.fillna(0)

    return burn_prob


def burn_prob_sol(
    num_soluciones, formato, filtro, input, corta_fuegos=False, id="fid", paisaje="test\\data_base\\proto.shp"
):
    """
    Calculate burn probability for multiple solutions over different periods.

    Args:
        num_soluciones (int): Number of solutions.
        formato (str): File format for the input data.
        filtro (list): List of filters for each solution and period.
        input (str): Path to the input directory.
        corta_fuegos (bool, optional): Whether to use fire breaks. Defaults to False.

    Returns:
        list: Nested list containing burn probabilities for each solution, rodal, and period.
    """
    periodos = config["horizonte"]
    bp = []
    temp_dir = tempfile.TemporaryDirectory()
    # Crear una nueva ruta para el directorio temporal
    temp_dir_path = Path(temp_dir.name)
    input_path = Path(input)

    # Iterar sobre todas las soluciones
    for s in range(num_soluciones):
        solucion_bp = []
        # Iterar sobre todos los periodos para la solución actual
        for t in range(periodos):
            # Construir la ruta al archivo utilizando f-strings y Path
            path_p = input_path / f"fuels_solucion_{s}_periodo_{t}{formato}"

            if path_p.exists():
                if corta_fuegos == False:
                    # Llamar a la función `burn_prob` con la ruta correcta
                    bp_rodales = burn_prob(str(path_p), str(temp_dir_path), None, paisaje)
                else:
                    fire_breaks = r".\\cortafuegos\\cortafuego_2%.tif"
                    bp_rodales = burn_prob(str(path_p), str(temp_dir_path), fire_breaks, paisaje)

            else:
                print(f"File {path_p} does not exist.")
                continue  # Saltar a la siguiente iteración si el archivo no existe

            bp_periodo = []
            for r in range(len(filtro[0])):
                # Filtrar por el 'fid' de cada rodal y obtener el valor de "_mean"
                bp_valor = bp_rodales.loc[bp_rodales[id] == filtro[s][r]["rid"], "_mean"].values
                if len(bp_valor) > 0:
                    bp_periodo.append(bp_valor[0])
                else:
                    bp_periodo.append(None)  # Manejar casos donde no se encuentra el 'fid'

            solucion_bp.append(bp_periodo)

        # Reorganizar para tener una lista de listas (por rodal) con valores por periodo
        reorganizado = list(map(list, zip(*solucion_bp)))

        # Calcular el promedio acumulado de cada valor con todos los periodos anteriores para esta solución
        promedios_solucion = []
        for fila in reorganizado:
            promedios_fila = []
            suma_acumulada = 0  # Para llevar el seguimiento de la suma de valores
            for i, valor in enumerate(fila):
                if valor is not None:
                    suma_acumulada += valor
                    promedio = suma_acumulada / (i + 1)
                else:
                    promedio = None  # Si el valor es None, el promedio también es None
                promedios_fila.append(promedio)

            promedios_solucion.append(promedios_fila)

        # Guardar los promedios de la solución actual en la lista final
        bp.append(promedios_solucion)

    return bp  # Devuelve bp[s][r][t] donde s es la solución, r es el rodal y t el periodo


def fuels_creation(gdf, filtro, output, id="fid"):
    """Crea los combustibles a partir de geopandas y los filtros de las soluciones (los combustibles de las soluciones)s"""
    gdf_temp = gdf.copy()
    periodos = config["horizonte"]
    base_dir = Path(output)

    for s in range(len(filtro)):  # soluciones
        for t in range(periodos):
            for r in range(len(filtro[0])):  # rodales
                gdf_temp.loc[gdf_temp[id] == filtro[s][r]["rid"], "kitral_cod"] = filtro[s][r]["codigo_kitral"][t]
            # Directorio base

            temp_dir = tempfile.TemporaryDirectory()
            # Crear un objeto Path para el archivo temporal .shp
            shp_path = Path(temp_dir.name) / "temp_file.shp"
            # Guardar el GeoDataFrame como un shapefile
            gdf_temp.to_file(shp_path)

            # Nombre del archivo con variables dinámicas
            file_name = f"fuels_solucion_{s}_periodo_{t}.tif"
            # Ruta completa al archivo

            base_path = base_dir / file_name

            # Eliminar el archivo si ya existe para asegurarse de que se reescriba
            if base_path.exists():
                base_path.unlink()

            fuels_tif(str(shp_path), "kitral_cod", base_path)
    print("combustibles en carpeta de soluciones")


def protection_value(path_fuels, path_biomass):
    """
    Calculate the protection value using the specified fuel and biomass rasters."""
    from fire2a.raster import read_raster

    result = processing.run(
        "fire2a:cell2firesimulator",
        {
            "CbdRaster": None,
            "CbhRaster": None,
            "CcfRaster": None,
            "DryRun": False,
            "ElevationRaster": None,
            "EnableCrownFire": False,
            "FireBreaksRaster": None,
            "FoliarMoistureContent": 66,
            "FuelModel": 1,
            "FuelRaster": path_fuels,
            "IgnitionMode": 0,
            "IgnitionPointVectorLayer": None,
            "IgnitionProbabilityMap": None,
            "IgnitionRadius": 0,
            "InstanceDirectory": "TEMPORARY_OUTPUT",
            "InstanceInProject": False,
            "LiveAndDeadFuelMoistureContentScenario": 2,
            "NumberOfSimulations": 50,
            "OtherCliArgs": "",
            "OutputOptions": [1, 2, 3, 4],
            "RandomNumberGeneratorSeed": 123,
            "ResultsDirectory": "TEMPORARY_OUTPUT",
            "ResultsInInstance": True,
            "SetFuelLayerStyle": False,
            "SimulationThreads": 15,
            "WeatherDirectory": "",
            "WeatherFile": ".\\example\\Weather.csv",
            "WeatherMode": 0,
        },
    )
    if rd := result.get("ResultsDirectory"):
        pass
    else:
        print("eerrrrr")

    bundle = processing.run(
        "fire2a:simulationresultsprocessing",
        {
            "BaseLayer": path_fuels,
            "EnablePropagationDiGraph": True,
            "EnablePropagationScars": False,
            "OutputDirectory": "TEMPORARY_OUTPUT",
            "ResultsDirectory": result["ResultsDirectory"],
        },
    )

    messages = "Messages\\messages.pickle"
    message_path = str(Path(result["ResultsDirectory"]) / messages)

    protection = processing.run(
        "fire2a:downstreamprotectionvaluepropagationmetric",
        {
            "NoBurnFill": True,
            "PickledMessages": message_path,
            "ProtectionValueRaster": path_biomass,
            "RasterOutput": "TEMPORARY_OUTPUT",
            "Scaling": True,
            "Threads": 15,
        },
    )
    protection_value, r_info = read_raster(protection["RasterOutput"])

    return protection_value, r_info


def fuels_creation_cortafuegos(gdf, caso_base):
    """Crea los combustibles y biomasa a partir de geopandas y los filtros del caso base (sin ningun manejo)"""
    gdf_temp = gdf.copy()
    periodos = config["horizonte"]
    base_dir_biomass = Path("./cortafuegos/biomass")
    base_dir_fuels = Path("./cortafuegos/fuels")
    gdf_temp["biomass"] = 0

    for t in range(periodos):
        for r in range(len(caso_base)):  # rodales
            gdf_temp.loc[gdf_temp["fid"] == caso_base[r]["rid"], "kitral_cod"] = caso_base[r]["codigo_kitral"][t]
            gdf_temp.loc[gdf_temp["fid"] == caso_base[r]["rid"], "biomass"] = caso_base[r]["biomass"][t]
        # Directorio base

        temp_dir = tempfile.TemporaryDirectory()
        # Crear un objeto Path para el archivo temporal .shp
        shp_path = Path(temp_dir.name) / "temp_file.shp"
        # Guardar el GeoDataFrame como un shapefile
        gdf_temp.to_file(shp_path)

        # Nombre del archivo con variables dinámicas
        file_name_fuels = f"fuels_base_periodo_{t}.tif"
        file_name_biomass = f"biomass_base_periodo_{t}.tif"
        # Ruta completa al archivo

        base_path_fuels = base_dir_fuels / file_name_fuels
        base_path_biomass = base_dir_biomass / file_name_biomass

        # Eliminar el archivo si ya existe para asegurarse de que se reescriba
        if base_path_biomass.exists():
            base_path_biomass.unlink()
        if base_path_fuels.exists():
            base_path_fuels.unlink()

        fuels_tif(shp_path, "kitral_cod", base_path_fuels)  # se escribe los fuels
        fuels_tif(shp_path, "biomass", base_path_biomass)  # se escriben los biomass
    print("combustibles en  carpeta cortafuegos/fuels y biomasa en carpeta de cortafuegos/biomass")


def create_protection_value_shp():
    """Crea el raster de proteccion a partir de los combustibles y biomasa generados, donde primero quema y despues calcula el DPV, para terminar calculando su valor presente"""
    periodos = config["horizonte"]
    dpv = []

    for t in range(periodos):
        base_path_fuels = Path("cortafuegos") / f"fuels\\fuels_base_periodo_{t}.tif"
        base_path_biomass = Path("cortafuegos") / f"biomass\\biomass_base_periodo_{t}.tif"
        dpv_periodo, info = protection_value(str(base_path_fuels), str(base_path_biomass))
        dpv.append(dpv_periodo)

    # Tasa de descuento
    tasa_descuento = config_opti["opti"]["tasa"]  # 10%|
    # Inicializar el VAN con ceros del mismo tamaño que los arreglos
    van_result = np.zeros(dpv[0].shape)

    # Calcular el VAN punto por punto
    for t, arr in enumerate(dpv):
        van_result += arr / (1 + tasa_descuento) ** t

    from fire2a.raster import write_raster

    # preguntar, ese optimizador lo hace respecto a rodal o pixel, ademas como agregarle un raster como columna al shp (puedo sacar promedio igual pero queria saber si hay una mejor manera)
    nombre_archivo = Path("cortafuegos") / "protection_value.tif"
    write_raster(van_result, nombre_archivo, "Gtiff", "EPSG:32718", info["Transform"])
    # Guardar los promedios de la solución actual en la lista final

    print("shp con protecition value en carpeta cortafuegos")
