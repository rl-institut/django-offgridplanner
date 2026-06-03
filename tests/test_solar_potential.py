import pandas as pd
import pvlib
import pytest

from offgridplanner.optimization.supply.solar_potential import _get_dc_feed_in
from offgridplanner.optimization.supply.solar_potential import (
    get_dc_feed_in_sync_db_query,
)

LAT = 10.0
LON = 20.0


@pytest.fixture
def clearsky_weather():
    """24-hour clearsky weather DataFrame suitable for pvlib ModelChain."""
    times = pd.date_range("2022-06-01", periods=24, freq="h", tz="UTC")
    location = pvlib.location.Location(LAT, LON)
    weather = location.get_clearsky(times).copy()
    weather["temp_air"] = 25.0
    weather["wind_speed"] = 2.0
    return weather


@pytest.fixture
def dt_index():
    return pd.date_range("2022-06-01", periods=24, freq="h")


# ---------- _get_dc_feed_in ----------


class TestGetDcFeedIn:
    def test_returns_series(self, clearsky_weather):
        result = _get_dc_feed_in(LAT, LON, clearsky_weather)
        assert isinstance(result, pd.Series)

    def test_length_matches_input(self, clearsky_weather):
        result = _get_dc_feed_in(LAT, LON, clearsky_weather)
        assert len(result) == len(clearsky_weather)

    def test_values_non_negative(self, clearsky_weather):
        result = _get_dc_feed_in(LAT, LON, clearsky_weather)
        assert (result >= 0).all()

    def test_daytime_output_is_positive(self, clearsky_weather):
        result = _get_dc_feed_in(LAT, LON, clearsky_weather)
        assert result.max() > 0


# ---------- get_dc_feed_in_sync_db_query ----------


class TestGetDcFeedInSyncDbQuery:
    def test_returns_series_from_weather_api(self, clearsky_weather, dt_index):
        from unittest.mock import MagicMock
        from unittest.mock import patch

        with (
            patch(
                "offgridplanner.optimization.supply.solar_potential.build_xarray_for_pvlib",
                return_value=MagicMock(),
            ),
            patch(
                "offgridplanner.optimization.supply.solar_potential.prepare_weather_data",
                return_value=clearsky_weather,
            ),
        ):
            result = get_dc_feed_in_sync_db_query(LAT, LON, dt_index)

        assert isinstance(result, pd.Series)
        assert len(result) == len(dt_index)

    def test_values_non_negative_from_weather_api(self, clearsky_weather, dt_index):
        from unittest.mock import MagicMock
        from unittest.mock import patch

        with (
            patch(
                "offgridplanner.optimization.supply.solar_potential.build_xarray_for_pvlib",
                return_value=MagicMock(),
            ),
            patch(
                "offgridplanner.optimization.supply.solar_potential.prepare_weather_data",
                return_value=clearsky_weather,
            ),
        ):
            result = get_dc_feed_in_sync_db_query(LAT, LON, dt_index)

        assert (result >= 0).all()

    def test_falls_back_to_renewables_ninja_on_api_error(self, dt_index):
        from unittest.mock import patch

        fallback = pd.Series([0.1] * len(dt_index), index=dt_index)

        with (
            patch(
                "offgridplanner.optimization.supply.solar_potential.build_xarray_for_pvlib",
                side_effect=RuntimeError("API failure"),
            ),
            patch(
                "offgridplanner.optimization.supply.solar_potential.request_renewables_ninja_pv_output",
                return_value={"electricity": fallback},
            ),
        ):
            result = get_dc_feed_in_sync_db_query(LAT, LON, dt_index)

        assert isinstance(result, pd.Series)
        assert len(result) == len(dt_index)
