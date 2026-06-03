import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pandas as pd
import pytest

from offgridplanner.optimization.requests import check_opt_type
from offgridplanner.optimization.requests import optimization_check_status
from offgridplanner.optimization.requests import optimization_server_request
from offgridplanner.optimization.requests import request_renewables_ninja_pv_output
from offgridplanner.optimization.requests import request_weather_data

# ---------- check_opt_type ----------


class TestCheckOptType:
    def test_grid_is_valid(self):
        check_opt_type("grid")

    def test_supply_is_valid(self):
        check_opt_type("supply")

    def test_invalid_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid simulation type"):
            check_opt_type("invalid")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid simulation type"):
            check_opt_type("")


# ---------- optimization_server_request ----------


class TestOptimizationServerRequest:
    @pytest.fixture
    def mock_response(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.text = json.dumps({"token": "abc123"})
        return response

    def test_grid_request_returns_parsed_json(self, mock_response):
        with patch(
            "offgridplanner.optimization.requests.httpx.post",
            return_value=mock_response,
        ):
            result = optimization_server_request({"key": "val"}, "grid")
        assert result == {"token": "abc123"}

    def test_supply_request_returns_parsed_json(self, mock_response):
        with patch(
            "offgridplanner.optimization.requests.httpx.post",
            return_value=mock_response,
        ):
            result = optimization_server_request({"key": "val"}, "supply")
        assert result == {"token": "abc123"}

    def test_invalid_opt_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid simulation type"):
            optimization_server_request({}, "invalid")

    def test_http_error_raises_runtime_error(self):
        import httpx

        with (
            patch(
                "offgridplanner.optimization.requests.httpx.post",
                side_effect=httpx.HTTPError("connection failed"),
            ),
            pytest.raises(RuntimeError),
        ):
            optimization_server_request({}, "grid")


# ---------- optimization_check_status ----------


class TestOptimizationCheckStatus:
    def test_returns_parsed_json_on_success(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.text = json.dumps({"status": "finished"})

        with patch(
            "offgridplanner.optimization.requests.httpx.get", return_value=response
        ):
            result = optimization_check_status("token123")

        assert result == {"status": "finished"}

    def test_returns_none_on_http_error(self):
        import httpx

        with patch(
            "offgridplanner.optimization.requests.httpx.get",
            side_effect=httpx.HTTPError("bad response"),
        ):
            result = optimization_check_status("token123")

        assert result is None

    def test_returns_none_on_unexpected_error(self):
        with patch(
            "offgridplanner.optimization.requests.httpx.get",
            side_effect=RuntimeError("unexpected"),
        ):
            result = optimization_check_status("token123")

        assert result is None


# ---------- request_renewables_ninja_pv_output ----------


class TestRequestRenewablesNinjaPvOutput:
    @pytest.fixture
    def mock_ninja_response(self):
        data = {
            "2019-01-01 00:00:00": {"electricity": 0.0},
            "2019-01-01 01:00:00": {"electricity": 0.5},
        }
        response = MagicMock()
        response.text = json.dumps({"data": data})
        return response

    def test_returns_dataframe(self, mock_ninja_response):
        with patch(
            "offgridplanner.optimization.requests.httpx.get",
            return_value=mock_ninja_response,
        ):
            result = request_renewables_ninja_pv_output(10.0, 20.0)

        assert isinstance(result, pd.DataFrame)

    def test_electricity_column_present(self, mock_ninja_response):
        with patch(
            "offgridplanner.optimization.requests.httpx.get",
            return_value=mock_ninja_response,
        ):
            result = request_renewables_ninja_pv_output(10.0, 20.0)

        assert "electricity" in result.columns

    def test_row_count_matches_data(self, mock_ninja_response):
        with patch(
            "offgridplanner.optimization.requests.httpx.get",
            return_value=mock_ninja_response,
        ):
            result = request_renewables_ninja_pv_output(10.0, 20.0)

        assert len(result) == 2  # noqa: PLR2004


# ---------- request_weather_data ----------


class TestRequestWeatherData:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        csrf_response = MagicMock()
        csrf_response.json.return_value = {"csrfToken": "test_token"}
        post_response = MagicMock()
        post_response.ok = True
        post_response.json.return_value = {
            "variables": {
                "t2m": [293.0, 294.0],
                "ssrd": [0.0, 100.0],
            }
        }
        session.get.return_value = csrf_response
        session.post.return_value = post_response
        return session

    def test_returns_dataframe_on_success(self, mock_session):
        with patch(
            "offgridplanner.optimization.requests.requests.Session",
            return_value=mock_session,
        ):
            result = request_weather_data(10.0, 20.0)

        assert isinstance(result, pd.DataFrame)

    def test_columns_match_variables(self, mock_session):
        with patch(
            "offgridplanner.optimization.requests.requests.Session",
            return_value=mock_session,
        ):
            result = request_weather_data(10.0, 20.0)

        assert "t2m" in result.columns
        assert "ssrd" in result.columns

    def test_returns_empty_dataframe_on_failed_post(self, mock_session):
        mock_session.post.return_value.ok = False

        with patch(
            "offgridplanner.optimization.requests.requests.Session",
            return_value=mock_session,
        ):
            result = request_weather_data(10.0, 20.0)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_timeinfo_returns_tuple(self, mock_session):
        mock_session.post.return_value.json.return_value = {
            "variables": {"t2m": [293.0]},
            "time": ["2022-01-01T00:00:00"],
        }

        with patch(
            "offgridplanner.optimization.requests.requests.Session",
            return_value=mock_session,
        ):
            result = request_weather_data(10.0, 20.0, timeinfo=True)

        assert isinstance(result, tuple)
        df, timeindex = result
        assert isinstance(df, pd.DataFrame)
        assert timeindex == ["2022-01-01T00:00:00"]
