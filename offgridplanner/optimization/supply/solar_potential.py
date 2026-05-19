"""

This module focuses on acquiring and processing weather data for solar energy analysis. It includes functions for
creating a Climate Data Store API configuration file, downloading weather data from the ERA5 dataset for specific
countries and date ranges, and preparing this data for solar potential analysis using the pvlib library. Key
functionalities involve retrieving grid points from the dataset and calculating the direct current (DC) power output
of a photovoltaic (PV) system based on the weather data. The module's integration with pvlib and era5 libraries,
combined with detailed solar panel and inverter specifications, enables it to calculate solar potential time series
"""

import logging

import numpy as np
import pandas as pd
import pvlib
from feedinlib import era5
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import PVSystem
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

from offgridplanner.optimization.requests import request_renewables_ninja_pv_output
from offgridplanner.optimization.requests import request_weather_data

logger = logging.getLogger(__name__)


def prepare_weather_data(data_xr):
    df = era5.format_pvlib(data_xr)
    df = df.reset_index()
    df = df.rename(columns={"time": "dt", "latitude": "lat", "longitude": "lon"})
    df = df.set_index(["dt"])
    df["dni"] = np.nan
    lat = float(data_xr.latitude)
    lon = float(data_xr.longitude)
    solar_position = pvlib.solarposition.get_solarposition(
        time=df.index,
        latitude=lat,
        longitude=lon,
    )
    df["dni"] = pvlib.irradiance.dni(
        ghi=df["ghi"],
        dhi=df["dhi"],
        zenith=solar_position["apparent_zenith"],
    ).fillna(0)
    df = df.reset_index()
    df["dt"] = df["dt"] - pd.Timedelta("30min")
    df["dt"] = df["dt"].dt.tz_convert("UTC").dt.tz_localize(None)
    df.iloc[:, 3:] = (df.iloc[:, 3:] + 0.0000001).round(1)
    df.loc[:, "lon"] = df.loc[:, "lon"].round(3)
    df.loc[:, "lat"] = df.loc[:, "lat"].round(7)
    df = df.set_index("dt")
    return df


def build_xarray_for_pvlib(lat, lon, dt_index):
    era5_units = {
        "d2m": {"units": "K", "long_name": "2 metre dewpoint temperature"},
        "e": {"units": "m", "long_name": "Evaporation (water equivalent)"},
        "fdir": {
            "units": "J/m²",
            "long_name": "Total sky direct solar radiation at surface",
        },
        "fsr": {"units": "1", "long_name": "Fraction of solar radiation"},
        "sp": {"units": "Pa", "long_name": "Surface pressure"},
        "ssrd": {"units": "J/m²", "long_name": "Surface solar radiation downwards"},
        "t2m": {"units": "K", "long_name": "2 metre temperature"},
        "tp": {"units": "m", "long_name": "Total precipitation"},
        "u10": {"units": "m/s", "long_name": "10 metre U wind component"},
        "u100": {"units": "m/s", "long_name": "100 metre U wind component"},
        "v10": {"units": "m/s", "long_name": "10 metre V wind component"},
        "v100": {"units": "m/s", "long_name": "100 metre V wind component"},
    }

    df = request_weather_data(lat, lon)
    df.index = dt_index
    df.index.name = "time"
    ds = df.to_xarray()

    # Attach scalar coords for the site
    ds = ds.assign_coords(latitude=float(lat), longitude=float(lon))

    # Add ERA5-style attributes expected by pvlib
    for var, attrs in era5_units.items():
        if var in ds:
            ds[var] = ds[var].assign_attrs(attrs)

    return ds


def get_dc_feed_in_sync_db_query(lat, lon, dt_index):
    try:
        cds_data = build_xarray_for_pvlib(lat, lon, dt_index)
        weather_df = prepare_weather_data(cds_data)
        solar_potential = _get_dc_feed_in(lat, lon, weather_df)
    # If something goes wrong using the internal weather data API, request data from renewables.ninja instead (warning: results can vary)
    except Exception as e:  # noqa:BLE001
        logger.warning(
            "Could not fetch weather data from API, defaulted to renewables.ninja instead.",
            exc_info=True,
        )
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
