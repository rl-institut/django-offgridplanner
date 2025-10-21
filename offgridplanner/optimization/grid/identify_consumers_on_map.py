"""
This module provides functions to identify buildings in OpenStreetMap within user-specified areas. It retrieves
geographic data within specified latitude and longitude boundaries using the Overpass API, then processes this data
to create GeoJSON. Functions in the module convert latitude and longitude to XY coordinates, check if points are
within boundaries, and calculate building surface areas and mean coordinates. The module is designed to handle complex
geographic data processing tasks efficiently, extracting meaningful information like building locations and dimensions
from raw OpenStreetMap data.
"""

import datetime
import json
import logging
import math
import time
import urllib.request
from urllib.error import HTTPError

import numpy as np
from shapely import geometry

from offgridplanner.optimization.requests import fetch_buildings_data

logger = logging.getLogger(__name__)


def _fetch_overpass(bbox, timeout=2500):
    lat_min, lon_min, lat_max, lon_max = bbox
    base = "https://www.overpass-api.de/api/interpreter"
    query = (
        f"[out:json][timeout:{timeout}][bbox:{lat_min},{lon_min},{lat_max},{lon_max}];"
        f'way["building"="yes"];(._;>;);out;'
    )
    url_str = f"{base}?data={query}".replace(" ", "+")
    if not url_str.startswith(("http:", "https:")):
        err = "URL must start with 'http:' or 'https:'"
        raise ValueError(err)

    with urllib.request.urlopen(url_str) as resp:  # noqa: S310 (validated above)
        raw = resp.read().decode()
    if not raw:
        err = "Overpass did not return any data."
        raise RuntimeError(err)
    data = json.loads(raw)
    if "elements" not in data or not data["elements"]:
        err = "Overpass did not return any building data."
        raise RuntimeError(err)
    return data


def get_consumer_within_boundaries(df, engine="overpass"):
    min_latitude = df["latitude"].min()
    min_longitude = df["longitude"].min()
    max_latitude = df["latitude"].max()
    max_longitude = df["longitude"].max()
    bbox = [min_latitude, min_longitude, max_latitude, max_longitude]

    data = None

    if engine == "minigrid-explorer":
        try:
            mg_data = fetch_buildings_data(bbox)
            if not mg_data:
                err = "Minigrid returned no data."
                raise RuntimeError(err)  # noqa: TRY301
            data = mg_data
        except RuntimeError as e:
            logger.warning(
                "Minigrid-Explorer failed (%s). Falling back to Overpass...",
                e,
                exc_info=True,
            )
            # Fall through to Overpass

    if engine == "overpass" or data is None:
        try:
            data = _fetch_overpass(bbox)
        except (HTTPError, RuntimeError) as e:
            logger.warning("Overpass fetch failed: %s", e, exc_info=True)
            return None, None

    try:
        geojson_data = convert_overpass_json_to_geojson(data)
        building_coord, building_surface_areas = (
            obtain_areas_and_mean_coordinates_from_geojson(geojson_data)
        )
    except (KeyError, TypeError) as e:
        logger.warning("Failed to convert/process building data: %s", e, exc_info=True)
        return None, None

    # Filter to polygon drawn by user
    boundary = df.to_numpy().tolist()
    mask_building_within_boundaries = {
        key: is_point_in_boundaries(value, boundary)
        for key, value in building_coord.items()
    }
    building_coordinates_within_boundaries = {
        key: value
        for key, value in building_coord.items()
        if mask_building_within_boundaries.get(key, False)
    }
    return data, building_coordinates_within_boundaries


def convert_overpass_json_to_geojson(json_dict):
    """
    This function convert dict obtained using the overpass api into
    a GEOJSON dict containing only the polygons of the buildings.

    Parameters
    ----------
    json_dict (dict):
        dict obtained using the overpass api.
    """
    ts = time.time()
    timestamp = datetime.datetime.fromtimestamp(ts, tz=datetime.UTC).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    node_coordinates = {
        element["id"]: [element["lat"], element["lon"]]
        for element in json_dict["elements"]
        if element["type"] == "node"
    }

    geojson = {
        "type": "FeatureCollection",
        "generator": "overpass-ide, formatted by PeopleSun WP4 Tool",
        "timestamp": timestamp,
        "features": [
            {
                "type": "Feature",
                "property": {
                    "@id": f"{d['type']}/{d['id']}",
                    "building": "yes",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [node_coordinates[node] for node in d["nodes"]],
                    ],
                },
            }
            for d in json_dict["elements"]
            if d["type"] == "way"
        ],
    }
    return geojson


def obtain_areas_and_mean_coordinates_from_geojson(geojson: dict):
    building_mean_coordinates = {}
    building_surface_areas = {}

    if len(geojson["features"]) != 0:
        reference_coordinate = geojson["features"][0]["geometry"]["coordinates"][0][0]
        for building in geojson["features"]:
            latitudes_longitudes = list(building["geometry"]["coordinates"][0])
            latitudes = [x[0] for x in latitudes_longitudes]
            longitudes = [x[1] for x in latitudes_longitudes]
            mean_coord = [np.mean(latitudes), np.mean(longitudes)]
            xy_coordinates = [
                xy_coordinates_from_latitude_longitude(
                    latitude=latitudes_longitudes[edge][0],
                    longitude=latitudes_longitudes[edge][1],
                    ref_latitude=reference_coordinate[0],
                    ref_longitude=reference_coordinate[1],
                )
                for edge in range(len(latitudes))
            ]
            polygon = geometry.Polygon(xy_coordinates)
            area = polygon.area
            perimeter = polygon.length
            # TODO check what these magic numbers mean
            min_valid_area = 4
            compactness_lower_bound = 0.81
            compactness_upper_bound = 1.91
            max_compact_building_area = 8

            compactness = 4 * np.pi * area / (perimeter**2) if perimeter else 0
            if area > min_valid_area and not (
                compactness_lower_bound < compactness < compactness_upper_bound
                and area < max_compact_building_area
            ):
                building_mean_coordinates[building["property"]["@id"]] = mean_coord
                building_surface_areas[building["property"]["@id"]] = area
    return building_mean_coordinates, building_surface_areas


def obtain_mean_coordinates_from_geojson(df):
    """
    This function creates a dictionary with the 'id' of each building as a key
    and the mean location of the building as value in the form [lat, long].

    Parameters
    ----------
        geojson (dict):
            Dictionary containing the geojson data of the building of a
            specific area. Output of the
            tools.conversion.convert_overpass_json_to_geojson function.

    Returns
    -------
        Dict containing the 'id' of each building as a key
        and the mean loaction of the building as value in the form [long, lat].

        Dict containing the 'id' of each building as a key
    """
    if not df.empty:
        df1 = df[df["type"] == "way"]
        df2 = df[df["type"] == "node"].set_index("id")

        df2["lat_lon"] = list(zip(df2["lat"], df2["lon"], strict=False))
        index_to_lat_lon = df2["lat_lon"].to_dict()
        df1_exploded = df1.explode("nodes")
        df1_exploded["nodes"] = df1.explode("nodes")["nodes"].map(index_to_lat_lon)
        df1["nodes"] = df1_exploded.groupby(df1_exploded.index).agg({"nodes": list})
        building_mean_coordinates = {}
        if not df1.empty:
            for _row_idx, row in df1.iterrows():
                latitudes_longitudes = list(row["nodes"])
                latitudes = [x[0] for x in latitudes_longitudes]
                longitudes = [x[1] for x in latitudes_longitudes]
                mean_coord = [np.mean(latitudes), np.mean(longitudes)]
                building_mean_coordinates[row["id"]] = mean_coord
        return building_mean_coordinates
    return {}, {}


def is_point_in_boundaries(point_coordinates: tuple, boundaries: tuple):
    """
    Function that checks whether 2D point lies within boundaries

    Parameter
    ---------
    coordinates (list or tuple):
        Coordinates of the point in format [x, y]

    boundaries (list or tuple):
        Coordinates of the angle of the polygon forming the boundaries in format
        [[x1, y1], [x2, y2], ..., [xn, yn]] for a polygon with n vertices.
    """
    polygon = geometry.Polygon(boundaries)
    point = geometry.Point(point_coordinates)

    return polygon.contains(point)


def are_points_in_boundaries(df, boundaries):
    polygon = geometry.Polygon(boundaries)
    df["inside_boundary"] = df.apply(
        lambda row: polygon.contains(
            geometry.Point([row["latitude"], row["longitude"]]),
        ),
        axis=1,
    )
    return df["inside_boundary"]


def xy_coordinates_from_latitude_longitude(
    latitude,
    longitude,
    ref_latitude,
    ref_longitude,
):
    """This function converts (latitude, longitude) coordinates into (x, y)
    plane coordinates using a reference latitude and longitude.

    Parameters
    ----------
        latitude (float):
            Latitude (in degree) to be converted.

        longitude (float):
            Longitude (in degree) to be converted.

        ref_latitude (float):
            Reference latitude (in degree).

        ref_longitude (float):
            Reference longitude (in degree).

    Return
    ------
        (tuple):
            (x, y) plane coordinates.
    """

    r = 6371000  # Radius of the earth [m]
    latitude_rad = math.radians(latitude)
    longitude_rad = math.radians(longitude)
    ref_latitude_rad = math.radians(ref_latitude)
    ref_longitude_rad = math.radians(ref_longitude)

    x = r * (longitude_rad - ref_longitude_rad) * math.cos(ref_latitude)
    y = r * (latitude_rad - ref_latitude_rad)
    return x, y
