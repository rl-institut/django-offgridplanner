import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pandas as pd
import pytest

from offgridplanner.projects.helpers import convert_value
from offgridplanner.projects.helpers import format_column_names
from offgridplanner.projects.helpers import from_nested_dict
from offgridplanner.projects.helpers import get_exchange_rate
from offgridplanner.projects.helpers import is_ajax
from offgridplanner.projects.helpers import reorder_dict
from offgridplanner.steps.models import EnergySystemDesign
from offgridplanner.steps.models import GridDesign

# ---------- convert_value ----------


class TestConvertValue:
    def test_empty_string_returns_none(self):
        assert convert_value("", "float") is None
        assert convert_value("", "int") is None
        assert convert_value("", "str") is None

    def test_float_conversion(self):
        assert convert_value("3.14", "float") == 3.14  # noqa: PLR2004

    def test_int_conversion(self):
        assert convert_value("42", "int") == 42  # noqa: PLR2004

    def test_bool_conversion(self):
        assert convert_value("True", "bool") is True

    def test_str_conversion(self):
        assert convert_value("hello", "str") == "hello"

    def test_unsupported_type_raises_value_error(self):
        with pytest.raises(ValueError, match="not supported"):
            convert_value("x", "list")


# ---------- format_column_names ----------


class TestFormatColumnNames:
    def test_replaces_underscores_with_spaces_and_capitalizes(self):
        df = pd.DataFrame(columns=["some_column"])
        result = format_column_names(df)
        assert "Some column" in result.columns

    def test_capitalizes_first_character(self):
        df = pd.DataFrame(columns=["my_field"])
        result = format_column_names(df)
        assert "My field" in result.columns

    def test_already_clean_name_unchanged(self):
        df = pd.DataFrame(columns=["Name"])
        result = format_column_names(df)
        assert "Name" in result.columns

    def test_modifies_in_place_and_returns_df(self):
        df = pd.DataFrame(columns=["a_b"])
        result = format_column_names(df)
        assert result is df


# ---------- reorder_dict ----------


class TestReorderDict:
    def test_moves_item_to_later_position(self):
        d = {"a": 1, "b": 2, "c": 3}
        result = reorder_dict(d, old_index=0, new_index=2)
        assert list(result.keys()) == ["b", "c", "a"]

    def test_moves_item_to_earlier_position(self):
        d = {"a": 1, "b": 2, "c": 3}
        result = reorder_dict(d, old_index=2, new_index=0)
        assert list(result.keys()) == ["c", "a", "b"]

    def test_same_index_returns_unchanged_order(self):
        d = {"a": 1, "b": 2}
        result = reorder_dict(d, old_index=0, new_index=0)
        assert list(result.keys()) == ["a", "b"]

    def test_preserves_values(self):
        d = {"x": 10, "y": 20, "z": 30}
        result = reorder_dict(d, old_index=0, new_index=2)
        assert result["x"] == 10  # noqa: PLR2004
        assert result["y"] == 20  # noqa: PLR2004
        assert result["z"] == 30  # noqa: PLR2004


# ---------- is_ajax ----------


class TestIsAjax:
    def test_returns_true_for_xmlhttprequest_header(self):
        request = MagicMock()
        request.headers = {"x-requested-with": "XMLHttpRequest"}
        assert is_ajax(request) is True

    def test_returns_false_when_header_absent(self):
        request = MagicMock()
        request.headers = {}
        assert is_ajax(request) is False

    def test_returns_false_for_wrong_header_value(self):
        request = MagicMock()
        request.headers = {"x-requested-with": "fetch"}
        assert is_ajax(request) is False


# ---------- get_exchange_rate ----------


class TestGetExchangeRate:
    def test_default_currency_returns_one(self):
        from config.settings.base import DEFAULT_CURRENCY

        result = get_exchange_rate(DEFAULT_CURRENCY)
        assert result == 1.0

    def test_other_currency_uses_api(self):
        from config.settings.base import DEFAULT_CURRENCY

        # Use any currency that is not the default to exercise the HTTP branch
        test_currency = "NGN" if DEFAULT_CURRENCY != "NGN" else "USD"
        mock_response = MagicMock()
        mock_response.json.return_value = {"conversion_rates": {test_currency: 1.08}}

        with patch(
            "offgridplanner.projects.helpers.httpx.get", return_value=mock_response
        ):
            result = get_exchange_rate(test_currency)

        assert result == 1.08  # noqa: PLR2004

    def test_unknown_currency_returns_fallback_one(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"conversion_rates": {}}

        with patch(
            "offgridplanner.projects.helpers.httpx.get", return_value=mock_response
        ):
            result = get_exchange_rate("XYZ")

        assert result == 1.0


# ---------- from_nested_dict ----------


class TestFromNestedDict:
    def test_flat_grid_design_field_mapped_correctly(self):
        # GridDesign has db_column="distribution_cable__lifetime"
        # from_nested_dict should map it to field name "distribution_cable_lifetime"
        nested = {
            "distribution_cable": {"lifetime": 20, "capex": 1.5, "max_length": 100.0}
        }
        result = from_nested_dict(GridDesign, nested)
        assert result.get("distribution_cable_lifetime") == 20  # noqa: PLR2004

    def test_unknown_keys_are_ignored(self):
        nested = {"nonexistent_component": {"value": 99}}
        result = from_nested_dict(GridDesign, nested)
        assert result == {}

    def test_percentage_fields_scaled_by_100(self):
        # EnergySystemDesign has battery__parameters__efficiency (percentage field)
        nested = {"battery": {"parameters": {"efficiency": 0.9}}}
        result = from_nested_dict(EnergySystemDesign, nested)
        # efficiency is a percentage field: stored value should be 0.9 * 100 = 90
        assert result.get("battery_parameters_efficiency") == pytest.approx(90.0)

    def test_non_percentage_field_not_scaled(self):
        nested = {"battery": {"parameters": {"nominal_capacity": 50.0}}}
        result = from_nested_dict(EnergySystemDesign, nested)
        assert result.get("battery_parameters_nominal_capacity") == pytest.approx(50.0)

    def test_roundtrip_grid_design(self):
        # to_nested_dict then from_nested_dict should recover the original field values
        gd = GridDesign(
            distribution_cable_lifetime=20,
            distribution_cable_capex=1.5,
            distribution_cable_max_length=100.0,
        )
        nested = gd.to_nested_dict()
        result = from_nested_dict(GridDesign, json.loads(json.dumps(nested)))
        assert result.get("distribution_cable_lifetime") == 20  # noqa: PLR2004
        assert result.get("distribution_cable_capex") == pytest.approx(1.5)
