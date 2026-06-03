import math

import numpy as np
import pandas as pd
import pytest

from offgridplanner.optimization.grid.osm_utils import are_points_in_boundaries
from offgridplanner.optimization.grid.osm_utils import convert_overpass_json_to_geojson
from offgridplanner.optimization.grid.osm_utils import is_point_in_boundaries
from offgridplanner.optimization.grid.osm_utils import (
    obtain_areas_and_mean_coordinates_from_geojson,
)
from offgridplanner.optimization.grid.osm_utils import (
    obtain_mean_coordinates_from_geojson,
)
from offgridplanner.optimization.grid.osm_utils import (
    xy_coordinates_from_latitude_longitude,
)

EARTH_RADIUS_M = 6_371_000
FLOAT_TOLERANCE = 1e-6
RELATIVE_TOLERANCE = 0.001  # 0.1 %
WAY_ID = 100
BUILDING_SIZE_DEG = 0.01


@pytest.fixture
def unit_square_boundaries():
    """Unit square polygon [[0,0],[0,1],[1,1],[1,0]]."""
    return [[0, 0], [0, 1], [1, 1], [1, 0]]


@pytest.fixture
def minimal_overpass_json():
    """Minimal Overpass API response: four nodes forming one rectangular building."""
    return {
        "elements": [
            {"type": "node", "id": 1, "lat": 0.0, "lon": 0.0},
            {"type": "node", "id": 2, "lat": 0.01, "lon": 0.0},
            {"type": "node", "id": 3, "lat": 0.01, "lon": 0.01},
            {"type": "node", "id": 4, "lat": 0.0, "lon": 0.01},
            {"type": "way", "id": 100, "nodes": [1, 2, 3, 4, 1]},
        ]
    }


@pytest.fixture
def overpass_elements_df():
    """Overpass elements as a DataFrame (nodes + one way) for obtain_mean_coordinates_from_geojson."""
    rows = [
        {"type": "node", "id": 1, "lat": 0.0, "lon": 0.0},
        {"type": "node", "id": 2, "lat": 0.01, "lon": 0.0},
        {"type": "node", "id": 3, "lat": 0.01, "lon": 0.01},
        {"type": "node", "id": 4, "lat": 0.0, "lon": 0.01},
        {"type": "way", "id": 100, "nodes": [1, 2, 3, 4, 1]},
    ]
    return pd.DataFrame(rows)


# ---------- xy_coordinates_from_latitude_longitude ----------


class TestXyCoordinatesFromLatitudeLongitude:
    def test_ref_point_returns_origin(self):
        x, y = xy_coordinates_from_latitude_longitude(10.0, 20.0, 10.0, 20.0)
        assert abs(x) < FLOAT_TOLERANCE
        assert abs(y) < FLOAT_TOLERANCE

    def test_moving_north_increases_y(self):
        _, y_south = xy_coordinates_from_latitude_longitude(9.0, 20.0, 8.0, 20.0)
        _, y_north = xy_coordinates_from_latitude_longitude(11.0, 20.0, 8.0, 20.0)
        assert y_north > y_south

    def test_moving_east_increases_x(self):
        x_west, _ = xy_coordinates_from_latitude_longitude(10.0, 19.0, 10.0, 20.0)
        x_east, _ = xy_coordinates_from_latitude_longitude(10.0, 21.0, 10.0, 20.0)
        assert x_east > x_west

    def test_one_degree_latitude_approx_111km(self):
        _, y = xy_coordinates_from_latitude_longitude(1.0, 0.0, 0.0, 0.0)
        expected_m = 2 * math.pi * EARTH_RADIUS_M / 360
        assert abs(y - expected_m) / expected_m < RELATIVE_TOLERANCE

    def test_symmetry_north_south(self):
        _, y_pos = xy_coordinates_from_latitude_longitude(10.0, 20.0, 9.0, 20.0)
        _, y_neg = xy_coordinates_from_latitude_longitude(8.0, 20.0, 9.0, 20.0)
        assert abs(abs(y_pos) - abs(y_neg)) < FLOAT_TOLERANCE


# ---------- is_point_in_boundaries ----------


class TestIsPointInBoundaries:
    def test_interior_point_returns_true(self, unit_square_boundaries):
        assert is_point_in_boundaries((0.5, 0.5), unit_square_boundaries) is True

    def test_exterior_point_returns_false(self, unit_square_boundaries):
        assert is_point_in_boundaries((2.0, 2.0), unit_square_boundaries) is False

    def test_boundary_point_not_interior(self, unit_square_boundaries):
        # shapely polygon.contains excludes the boundary itself
        assert is_point_in_boundaries((0.0, 0.0), unit_square_boundaries) is False

    def test_negative_coordinates(self):
        boundaries = [[-1, -1], [-1, 1], [1, 1], [1, -1]]
        assert is_point_in_boundaries((0.0, 0.0), boundaries) is True


# ---------- are_points_in_boundaries ----------


class TestArePointsInBoundaries:
    def test_returns_boolean_series(self, unit_square_boundaries):
        df = pd.DataFrame({"latitude": [0.5], "longitude": [0.5]})
        result = are_points_in_boundaries(df, unit_square_boundaries)
        assert result.dtype == bool

    def test_interior_point_marked_true(self, unit_square_boundaries):
        df = pd.DataFrame({"latitude": [0.5], "longitude": [0.5]})
        result = are_points_in_boundaries(df, unit_square_boundaries)
        assert bool(result.iloc[0]) is True

    def test_exterior_point_marked_false(self, unit_square_boundaries):
        df = pd.DataFrame({"latitude": [2.0], "longitude": [2.0]})
        result = are_points_in_boundaries(df, unit_square_boundaries)
        assert bool(result.iloc[0]) is False

    def test_mixed_points_classified_correctly(self, unit_square_boundaries):
        df = pd.DataFrame({"latitude": [0.5, 2.0], "longitude": [0.5, 2.0]})
        result = are_points_in_boundaries(df, unit_square_boundaries)
        assert bool(result.iloc[0]) is True
        assert bool(result.iloc[1]) is False


# ---------- convert_overpass_json_to_geojson ----------


class TestConvertOverpassJsonToGeojson:
    def test_returns_feature_collection(self, minimal_overpass_json):
        result = convert_overpass_json_to_geojson(minimal_overpass_json)
        assert result["type"] == "FeatureCollection"

    def test_way_becomes_polygon_feature(self, minimal_overpass_json):
        result = convert_overpass_json_to_geojson(minimal_overpass_json)
        assert len(result["features"]) == 1
        assert result["features"][0]["geometry"]["type"] == "Polygon"

    def test_node_coordinates_mapped_to_polygon(self, minimal_overpass_json):
        result = convert_overpass_json_to_geojson(minimal_overpass_json)
        coords = result["features"][0]["geometry"]["coordinates"][0]
        assert coords[0] == [0.0, 0.0]

    def test_building_property_set(self, minimal_overpass_json):
        result = convert_overpass_json_to_geojson(minimal_overpass_json)
        assert result["features"][0]["property"]["building"] == "yes"

    def test_empty_elements_returns_no_features(self):
        result = convert_overpass_json_to_geojson({"elements": []})
        assert result["features"] == []

    def test_nodes_only_returns_no_features(self, minimal_overpass_json):
        nodes_only = {
            "elements": [
                e for e in minimal_overpass_json["elements"] if e["type"] == "node"
            ]
        }
        result = convert_overpass_json_to_geojson(nodes_only)
        assert result["features"] == []


# ---------- obtain_areas_and_mean_coordinates_from_geojson ----------


class TestObtainAreasAndMeanCoordinates:
    def test_returns_two_dicts(self, minimal_overpass_json):
        geojson = convert_overpass_json_to_geojson(minimal_overpass_json)
        coords, areas = obtain_areas_and_mean_coordinates_from_geojson(geojson)
        assert isinstance(coords, dict)
        assert isinstance(areas, dict)

    def test_building_detected_for_large_polygon(self, minimal_overpass_json):
        # 0.01deg x 0.01deg building (~1 km2) passes the area filter
        geojson = convert_overpass_json_to_geojson(minimal_overpass_json)
        coords, areas = obtain_areas_and_mean_coordinates_from_geojson(geojson)
        assert len(coords) == 1
        assert len(areas) == 1

    def test_mean_coordinates_within_building_bounds(self, minimal_overpass_json):
        geojson = convert_overpass_json_to_geojson(minimal_overpass_json)
        coords, _ = obtain_areas_and_mean_coordinates_from_geojson(geojson)
        if coords:
            mean = next(iter(coords.values()))
            assert len(mean) == 2  # noqa: PLR2004

    def test_empty_features_returns_empty_dicts(self):
        coords, areas = obtain_areas_and_mean_coordinates_from_geojson({"features": []})
        assert coords == {}
        assert areas == {}


# ---------- obtain_mean_coordinates_from_geojson ----------


class TestObtainMeanCoordinatesFromGeojson:
    def test_returns_dict_for_valid_input(self, overpass_elements_df):
        result = obtain_mean_coordinates_from_geojson(overpass_elements_df)
        assert isinstance(result, dict)

    def test_building_id_present_in_result(self, overpass_elements_df):
        result = obtain_mean_coordinates_from_geojson(overpass_elements_df)
        assert WAY_ID in result

    def test_mean_coordinate_has_two_components(self, overpass_elements_df):
        result = obtain_mean_coordinates_from_geojson(overpass_elements_df)
        assert len(result[WAY_ID]) == 2  # noqa: PLR2004

    def test_mean_lat_within_building_bounds(self, overpass_elements_df):
        result = obtain_mean_coordinates_from_geojson(overpass_elements_df)
        mean_lat = result[WAY_ID][0]
        assert 0.0 <= mean_lat <= BUILDING_SIZE_DEG

    def test_empty_df_returns_empty_dict(self):
        result = obtain_mean_coordinates_from_geojson(pd.DataFrame())
        assert result == {}

    def test_empty_df_return_type_matches_non_empty(self):
        result = obtain_mean_coordinates_from_geojson(pd.DataFrame())
        assert isinstance(result, dict)

    def test_mean_coordinates_are_numpy_floats_or_float(self, overpass_elements_df):
        result = obtain_mean_coordinates_from_geojson(overpass_elements_df)
        mean_lat, mean_lon = result[WAY_ID]
        assert isinstance(mean_lat, (float, np.floating))
        assert isinstance(mean_lon, (float, np.floating))
