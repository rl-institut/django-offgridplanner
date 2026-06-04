import pandas as pd

from offgridplanner.projects.exports import format_column_names
from offgridplanner.projects.exports import format_first_col

# ---------- format_first_col ----------


class TestFormatFirstCol:
    def _apply(self, values):
        df = pd.DataFrame({"col": values})
        return format_first_col(df)["col"].tolist()

    def test_replaces_underscores_with_spaces(self):
        result = self._apply(["n_poles"])
        assert result == ["N poles"]

    def test_capitalizes_first_character(self):
        result = self._apply(["peak_demand"])
        assert result == ["Peak demand"]

    def test_replaces_lcoe_with_uppercase(self):
        result = self._apply(["lcoe_share_grid"])
        assert result == ["LCOE share grid"]

    def test_replaces_pv_with_uppercase(self):
        result = self._apply(["pv_capacity"])
        assert result == ["PV capacity"]

    def test_replaces_co2_with_uppercase(self):
        result = self._apply(["co2_emissions"])
        assert result == ["CO2 emissions"]

    def test_replaces_mg_with_minigrid(self):
        result = self._apply(["mg_connection_cost"])
        assert result == ["Mini-grid connection cost"]

    def test_res_replaced_with_full_label(self):
        result = self._apply(["res"])
        assert result == ["RES share"]

    def test_returns_dataframe(self):
        df = pd.DataFrame({"col": ["n_poles"]})
        result = format_first_col(df)
        assert isinstance(result, pd.DataFrame)

    def test_does_not_affect_other_columns(self):
        df = pd.DataFrame({"col": ["pv_capacity"], "other": [42]})
        result = format_first_col(df)
        assert result["other"].iloc[0] == 42  # noqa: PLR2004


# ---------- format_column_names ----------


class TestFormatColumnNames:
    def test_replaces_underscores_with_spaces_and_capitalizes(self):
        df = pd.DataFrame(columns=["n_poles", "cost_grid"])
        result = format_column_names(df)
        assert "N poles" in result.columns
        assert "Cost grid" in result.columns

    def test_capitalizes_first_character(self):
        df = pd.DataFrame(columns=["peak_demand"])
        result = format_column_names(df)
        assert "Peak demand" in result.columns

    def test_already_formatted_column_unchanged(self):
        df = pd.DataFrame(columns=["Value"])
        result = format_column_names(df)
        assert "Value" in result.columns

    def test_returns_same_dataframe(self):
        df = pd.DataFrame(columns=["a_b"])
        result = format_column_names(df)
        assert result is df

    def test_multiple_underscores(self):
        df = pd.DataFrame(columns=["very_long_column_name"])
        result = format_column_names(df)
        assert "Very long column name" in result.columns
