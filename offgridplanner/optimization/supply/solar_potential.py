"""

This module focuses on acquiring and processing weather data for solar energy analysis. It includes functions for
creating a Climate Data Store API configuration file, downloading weather data from the ERA5 dataset for specific
countries and date ranges, and preparing this data for solar potential analysis using the pvlib library. Key
functionalities involve retrieving grid points from the dataset and calculating the direct current (DC) power output
of a photovoltaic (PV) system based on the weather data. The module's integration with pvlib and era5 libraries,
combined with detailed solar panel and inverter specifications, enables it to calculate solar potential time series
"""

import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pvlib
import pytz
from feedinlib import era5
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from config.settings.base import CDS_API_KEY
from offgridplanner.optimization.models import WeatherData
from offgridplanner.optimization.requests import request_renewables_ninja_pv_output

# TODO this will no longer be needed, for local try to mode from oginal ogp mySQL
# originally in sync_queries.py
# def update_weather_db(country='Nigeria', year=None):
#     if year is not None and year >= (pd.Timestamp.now() + pd.Timedelta(24 * 7, unit='H')).year:
#         raise Exception("This function excepts available weather data for a entire year, "
#                         "but for {} that data is not yet available".format(year))
#     elif year != 2022:
#         warnings.warn("Currently, only simulation the year 2022 is possible. Refer to the comments for "
#                       "detailed explanations.")
# year = (pd.Timestamp.now() + pd.Timedelta(24 * 14, unit='H')).year - 1 if year is None else int(year)
# year = 2022 # so fast demand data is only available for 2022 and start_date is always 2022-01-01 and max. duration
# # is one year (see func 'save_project_setup' in static/js/backend_communications.js )
# for month in range(1, 13, 3):  # Increment by 3
#     start_date = pd.Timestamp(year=year, month=month, day=1) - pd.Timedelta(25, unit='H')
#     end_month = month + 2  # Third month in the interval
#     end_month = 12 if end_month > 12 else end_month  # Ensure it does not exceed December
#     last_day_of_end_month = calendar.monthrange(year, end_month)[1]
#     end_date = pd.Timestamp(year=year, month=end_month, day=last_day_of_end_month) + pd.Timedelta(25, unit='H')
#     file_name = 'cfd_weather_data_{}.nc'.format(start_date.strftime('%Y-%m'))
#     data_xr = download_weather_data(start_date, end_date, country=country, target_file=file_name).copy()
#     df = prepare_weather_data(data_xr)
#     df.to_csv("weather_data.csv")
# insert_df(WeatherData, df)


# def insert_df(model_class, df, user_id=None, project_id=None):
#     if user_id is not None and project_id is not None:
#         user_id, project_id = int(user_id), int(project_id)
#     df = df.dropna(how='all', axis=0)
#     if not df.empty:
#         if user_id is not None and project_id is not None:
#             remove(model_class, user_id, project_id)
#             df['id'] = int(user_id)
#             df['project_id'] = int(project_id)
#         if hasattr(model_class, 'dt') and 'dt' not in df.columns:
#             df.index.name = 'dt'
#             df = df.reset_index()
#         _insert_df(model_class.__name__.lower(), df, if_exists='update')


# originally in sync_queries.py
def get_weather_data(lat, lon, start, end):
    index = pd.date_range(start, end, freq="h")

    ts_changed = False

    # if end > make_aware(pd.to_datetime("2023-03-01")):
    #     end = (pd.to_datetime(f"2022-{start.month}-{start.day}")) + (end - start)
    #     start = (pd.to_datetime(f"2022-{start.month}-{start.day}"))
    #     ts_changed = True

    closest_lat, closest_lon = get_closest_grid_point(lat, lon)

    # TODO the data in the DB is ty aware but set to UTC, we need to make the
    #  DB data not tz aware, in the meantime this fixes it
    qs = WeatherData.objects.filter(
        lat=closest_lat,
        lon=closest_lon,
        dt__range=(
            start.replace(tzinfo=pytz.timezone("UTC")),
            end.replace(tzinfo=pytz.timezone("UTC")),
        ),
    )
    # Convert QuerySet to DataFrame
    df = pd.DataFrame.from_records(qs.values()).set_index("dt").astype(float)

    # TODO the data is saved in DB as time-aware, right now we don't need this
    # TODO when n_days < 360, there is a length mismatch between the index and the db data, this is a quick fix but we should look at it properly later
    try:
        df.index = index
    except ValueError:
        df = df[:-1]
        df.index = index
    # if ts_changed:
    #     df.index = index

    return df


# originally in sync_queries.py
def get_closest_grid_point(lat, lon):
    # TODO handle this in a different way than with these hard-coded coords -
    #  prone to error and clunky to implement once we expand to other countries
    lats = pd.Series(
        [
            14.442,
            14.192,
            13.942,
            13.692,
            13.442,
            13.192,
            12.942,
            12.692,
            12.442,
            12.192,
            11.942,
            11.692,
            11.442,
            11.192,
            10.942,
            10.692,
            10.442,
            10.192,
            9.942,
            9.692,
            9.442,
            9.192,
            8.942,
            8.692,
            8.442,
            8.192,
            7.942,
            7.692,
            7.442,
            7.192,
            6.942,
            6.692,
            6.442,
            6.192,
            5.942,
            5.692,
            5.442,
            5.192,
            4.942,
            4.692,
            4.442,
            4.192,
            3.942,
            3.692,
            3.442,
            3.192,
            2.942,
            2.691,
        ],
    )
    lons = pd.Series(
        [
            4.24,
            4.490026,
            4.740053,
            4.990079,
            5.240105,
            5.490131,
            5.740158,
            5.990184,
            6.240211,
            6.490237,
            6.740263,
            6.99029,
            7.240316,
            7.490342,
            7.740368,
            7.990395,
            8.240421,
            8.490447,
            8.740474,
            8.9905,
            9.240526,
            9.490553,
            9.740579,
            9.990605,
            10.240631,
            10.490658,
            10.740685,
            10.99071,
            11.240737,
            11.490763,
            11.740789,
            11.990816,
            12.240842,
            12.490869,
            12.740894,
            12.990921,
            13.240948,
            13.490973,
            13.741,
        ],
    )
    closest_lat = round(lats.loc[(lats - lat).abs().idxmin()], 3)
    closest_lon = round(lons.loc[(lons - lon).abs().idxmin()], 3)
    return closest_lat, closest_lon


def create_cdsapirc_file():
    home_dir = Path("~").expanduser()
    file_path = Path(home_dir) / ".cdsapirc"
    if Path(file_path).exists:
        print(f".cdsapirc file already exists at {file_path}")
        return
    content = f"url: https://cds.climate.copernicus.eu/api/v2\nkey: {CDS_API_KEY}"
    with Path(file_path).open("w") as file:
        file.write(content)
    print(f".cdsapirc file created at {file_path}")


def download_weather_data(start_date, end_date, country="Nigeria", target_file="file"):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
    country_shape = world[world["name"] == country]
    geopoints = country_shape.geometry.iloc[0].bounds
    lat = [geopoints[0], geopoints[2]]
    lon = [geopoints[1], geopoints[3]]
    variable = "pvlib"
    create_cdsapirc_file()
    data_xr = era5.get_era5_data_from_datespan_and_position(
        variable=variable,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        latitude=lat,
        longitude=lon,
        target_file=target_file,
    )
    return data_xr


def prepare_weather_data(data_xr):
    df = era5.format_pvlib(data_xr)
    df = df.reset_index()
    df = df.rename(columns={"valid_time": "dt", "latitude": "lat", "longitude": "lon"})
    df = df.set_index(["dt"])
    df["dni"] = np.nan
    grid_points = retrieve_grid_points(data_xr)
    for lon, lat in grid_points:
        mask = (df["lat"] == lat) & (df["lon"] == lon)
        tmp_df = df.loc[mask]
        solar_position = pvlib.solarposition.get_solarposition(
            time=tmp_df.index,
            latitude=lat,
            longitude=lon,
        )
        df.loc[mask, "dni"] = pvlib.irradiance.dni(
            ghi=tmp_df["ghi"],
            dhi=tmp_df["dhi"],
            zenith=solar_position["apparent_zenith"],
        ).fillna(0)
    df = df.reset_index()
    df["dt"] = df["dt"] - pd.Timedelta("30min")
    df["dt"] = df["dt"].dt.tz_convert("UTC").dt.tz_localize(None)
    df.iloc[:, 3:] = (df.iloc[:, 3:] + 0.0000001).round(1)
    df.loc[:, "lon"] = df.loc[:, "lon"].round(3)
    df.loc[:, "lat"] = df.loc[:, "lat"].round(7)
    df.iloc[:, 1:] = df.iloc[:, 1:].astype(str)
    return df


def retrieve_grid_points(ds):
    lat = ds.variables["latitude"][:]
    lon = ds.variables["longitude"][:]
    lon_grid, lat_grid = np.meshgrid(lat, lon)
    grid_points = np.stack((lat_grid, lon_grid), axis=-1)
    grid_points = grid_points.reshape(-1, 2)
    return grid_points


def get_dc_feed_in_sync_db_query(lat, lon, dt_index):
    try:
        weather_df = get_weather_data(lat, lon, dt_index[0], dt_index[-1])
        solar_potential = _get_dc_feed_in(lat, lon, weather_df)
    # If the weather data db is not set up, send API call to renewables.ninja instead
    except KeyError:
        # TODO the results between the pvlib modeling and the RN potential output vary greatly, double check
        solar_potential = request_renewables_ninja_pv_output(lat, lon)["electricity"]
        solar_potential.index = dt_index
    return solar_potential


def _get_dc_feed_in(lat, lon, weather_df):
    module = pvlib.pvsystem.retrieve_sam("SandiaMod")[
        "SolarWorld_Sunmodule_250_Poly__2013_"
    ]
    inverter = pvlib.pvsystem.retrieve_sam("cecinverter")[
        "ABB__MICRO_0_25_I_OUTD_US_208__208V_"
    ]
    temperature_model_parameters = TEMPERATURE_MODEL_PARAMETERS["sapm"][
        "open_rack_glass_glass"
    ]
    system = PVSystem(
        surface_tilt=30,
        surface_azimuth=180,
        module_parameters=module,
        inverter_parameters=inverter,
        temperature_model_parameters=temperature_model_parameters,
    )
    location = Location(latitude=lat, longitude=lon)
    mc = ModelChain(system, location)
    mc.run_model(weather=weather_df)
    dc_power = mc.results.dc["p_mp"].clip(0).fillna(0) / 1000
    return dc_power
