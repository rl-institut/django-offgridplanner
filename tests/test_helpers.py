import io
from datetime import datetime

import pandas as pd
import pytest
from django.core.exceptions import ValidationError

from offgridplanner.optimization.helpers import check_imported_demand_data
from offgridplanner.optimization.helpers import check_missing_columns
from offgridplanner.optimization.helpers import consumer_data_to_file
from offgridplanner.optimization.helpers import convert_column_types
from offgridplanner.optimization.helpers import convert_file_to_df
from offgridplanner.optimization.helpers import df_to_file
from offgridplanner.optimization.helpers import set_default_values
from offgridplanner.optimization.helpers import validate_column_inputs
from offgridplanner.optimization.helpers import validate_file_extension

# n_days=1 → 24 required hourly timesteps
PROJECT_DICT_1DAY = {"n_days": 1, "start_date": datetime(2022, 1, 1)}  # noqa: DTZ001


# ---------- df_to_file ----------


class TestDfToFile:
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({"a": [1, 2], "b": [3, 4]})

    def test_csv_is_readable_string_io(self, sample_df):
        result = df_to_file(sample_df, "csv")
        content = result.read()
        assert "a" in content
        assert "b" in content

    def test_xlsx_is_non_empty_bytes_io(self, sample_df):
        result = df_to_file(sample_df, "xlsx")
        assert len(result.read()) > 0

    def test_unsupported_type_raises_value_error(self, sample_df):
        with pytest.raises(ValueError, match="not supported"):
            df_to_file(sample_df, "json")

    def test_csv_roundtrip(self, sample_df):
        result = df_to_file(sample_df, "csv")
        recovered = pd.read_csv(result)
        pd.testing.assert_frame_equal(recovered, sample_df)


# ---------- validate_file_extension ----------


class TestValidateFileExtension:
    def test_csv_is_valid(self):
        valid, ext = validate_file_extension("data.csv")
        assert valid is True
        assert ext == "csv"

    def test_xlsx_is_valid(self):
        valid, ext = validate_file_extension("data.xlsx")
        assert valid is True
        assert ext == "xlsx"

    def test_json_is_invalid(self):
        valid, _ = validate_file_extension("data.json")
        assert valid is False

    def test_extension_check_is_case_insensitive(self):
        valid, ext = validate_file_extension("DATA.CSV")
        assert valid is True
        assert ext == "csv"

    def test_returns_error_message_for_invalid(self):
        _, msg = validate_file_extension("data.txt")
        assert "Unsupported" in msg


# ---------- convert_file_to_df ----------


class TestConvertFileToDf:
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({"lat": [1.0, 2.0], "lon": [3.0, 4.0]})

    def test_csv_returns_dataframe(self, sample_df):
        csv_bytes = io.BytesIO(sample_df.to_csv(index=False).encode("utf-8"))
        result = convert_file_to_df(csv_bytes, "csv")
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["lat", "lon"]

    def test_xlsx_returns_dataframe(self, sample_df):
        xlsx_buf = io.BytesIO()
        sample_df.to_excel(xlsx_buf, index=False, engine="xlsxwriter")
        xlsx_buf.seek(0)
        result = convert_file_to_df(xlsx_buf, "xlsx")
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["lat", "lon"]

    def test_csv_values_preserved(self, sample_df):
        csv_bytes = io.BytesIO(sample_df.to_csv(index=False).encode("utf-8"))
        result = convert_file_to_df(csv_bytes, "csv")
        pd.testing.assert_frame_equal(result, sample_df)


# ---------- check_missing_columns ----------


class TestCheckMissingColumns:
    def test_all_columns_present_does_not_raise(self):
        df = pd.DataFrame({"latitude": [], "longitude": []})
        check_missing_columns(df, ["latitude", "longitude"])

    def test_missing_column_raises_validation_error(self):
        df = pd.DataFrame({"latitude": []})
        with pytest.raises(ValidationError):
            check_missing_columns(df, ["latitude", "longitude"])

    def test_strips_and_lowercases_column_names(self):
        df = pd.DataFrame({"  Latitude  ": [], "  LONGITUDE  ": []})
        check_missing_columns(df, ["latitude", "longitude"])


# ---------- set_default_values ----------


class TestSetDefaultValues:
    def test_fills_none_with_default(self):
        df = pd.DataFrame({"a": [1.0, None]})
        result = set_default_values(df, {"a": 99.0})
        assert result["a"].iloc[1] == 99.0  # noqa: PLR2004

    def test_replaces_empty_string_then_applies_default(self):
        df = pd.DataFrame({"consumer_type": ["household", ""]})
        result = set_default_values(df, {"consumer_type": "enterprise"})
        assert result["consumer_type"].iloc[1] == "enterprise"

    def test_existing_values_are_preserved(self):
        df = pd.DataFrame({"a": [1.0, 2.0]})
        result = set_default_values(df, {"a": 99.0})
        assert result["a"].iloc[0] == 1.0
        assert result["a"].iloc[1] == 2.0  # noqa: PLR2004

    def test_unknown_default_column_is_ignored(self):
        df = pd.DataFrame({"a": [1.0]})
        result = set_default_values(df, {"a": 0.0, "nonexistent": 99.0})
        assert "nonexistent" not in result.columns


# ---------- validate_column_inputs ----------


class TestValidateColumnInputs:
    def test_valid_consumer_types_do_not_raise(self):
        validate_column_inputs(
            {"household", "enterprise", "public_service"}, "consumer_type"
        )

    def test_invalid_consumer_type_raises_validation_error(self):
        with pytest.raises(ValidationError):
            validate_column_inputs({"invalid_type"}, "consumer_type")

    def test_valid_shs_options_do_not_raise(self):
        validate_column_inputs({0, 1}, "shs_options")

    def test_invalid_shs_option_raises_validation_error(self):
        with pytest.raises(ValidationError):
            validate_column_inputs({2}, "shs_options")

    def test_empty_string_valid_for_consumer_detail(self):
        validate_column_inputs({""}, "consumer_detail")


# ---------- convert_column_types ----------


class TestConvertColumnTypes:
    def test_successful_type_conversion(self):
        df = pd.DataFrame({"lat": ["1.5", "2.3"]})
        result = convert_column_types(df, {"lat": float})
        assert result["lat"].dtype == float

    def test_invalid_value_raises_validation_error(self):
        df = pd.DataFrame({"lat": ["not_a_float"]})
        with pytest.raises(ValidationError):
            convert_column_types(df, {"lat": float})

    def test_int_conversion(self):
        df = pd.DataFrame({"count": ["10", "20"]})
        result = convert_column_types(df, {"count": int})
        assert result["count"].dtype == int


# ---------- consumer_data_to_file ----------


class TestConsumerDataToFile:
    def test_empty_df_returns_template_with_expected_columns(self):
        result = consumer_data_to_file(pd.DataFrame(), "csv")
        content = result.read()
        for col in ["latitude", "longitude", "consumer_type", "custom_specification"]:
            assert col in content

    def test_non_empty_df_drops_internal_columns(self):
        df = pd.DataFrame(
            {
                "latitude": [1.0],
                "longitude": [2.0],
                "consumer_type": ["household"],
                "custom_specification": [""],
                "shs_options": [0],
                "consumer_detail": ["default"],
                "is_connected": [True],
                "how_added": ["manual"],
                "node_type": ["consumer"],
            }
        )
        result = consumer_data_to_file(df, "csv")
        content = result.read()
        assert "is_connected" not in content
        assert "how_added" not in content
        assert "node_type" not in content

    def test_non_empty_df_preserves_public_columns(self):
        df = pd.DataFrame(
            {
                "latitude": [1.0],
                "longitude": [2.0],
                "consumer_type": ["household"],
                "custom_specification": [""],
                "shs_options": [0],
                "consumer_detail": ["default"],
                "is_connected": [True],
                "how_added": ["manual"],
                "node_type": ["consumer"],
            }
        )
        result = consumer_data_to_file(df, "csv")
        content = result.read()
        assert "latitude" in content
        assert "consumer_type" in content


# ---------- check_imported_demand_data ----------


class TestCheckImportedDemandData:
    def test_valid_data_returns_dataframe_and_no_error(self):
        df = pd.DataFrame({"demand": [1.0] * 24})
        result_df, error = check_imported_demand_data(df, PROJECT_DICT_1DAY)
        assert error == ""
        assert isinstance(result_df, pd.DataFrame)
        assert "demand" in result_df.columns

    def test_valid_data_length_matches_simulation_period(self):
        n_hours = 24  # n_days=1
        df = pd.DataFrame({"demand": [1.0] * n_hours})
        result_df, error = check_imported_demand_data(df, PROJECT_DICT_1DAY)
        assert error == ""
        assert len(result_df) == n_hours

    def test_empty_df_returns_none_and_error(self):
        result_df, error = check_imported_demand_data(pd.DataFrame(), PROJECT_DICT_1DAY)
        assert result_df is None
        assert error

    def test_missing_demand_column_returns_error(self):
        df = pd.DataFrame({"not_demand": [1.0] * 24})
        result_df, error = check_imported_demand_data(df, PROJECT_DICT_1DAY)
        assert result_df is None
        assert "demand" in error.lower()

    def test_insufficient_rows_returns_error(self):
        df = pd.DataFrame({"demand": [1.0] * 5})
        result_df, error = check_imported_demand_data(df, PROJECT_DICT_1DAY)
        assert result_df is None
        assert "data points" in error

    def test_excess_rows_trimmed_to_simulation_period(self):
        n_hours = 24
        df = pd.DataFrame({"demand": [1.0] * 100})
        result_df, error = check_imported_demand_data(df, PROJECT_DICT_1DAY)
        assert error == ""
        assert len(result_df) == n_hours

    def test_non_numeric_demand_returns_error(self):
        df = pd.DataFrame({"demand": ["not_a_number"] * 24})
        result_df, error = check_imported_demand_data(df, PROJECT_DICT_1DAY)
        assert result_df is None
        assert error
