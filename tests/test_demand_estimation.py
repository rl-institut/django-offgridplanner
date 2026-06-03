import json
from pathlib import Path

import pandas as pd
import pytest

from config.settings.base import EXAMPLE_PROJECT_PATH
from offgridplanner.optimization.models import Nodes
from offgridplanner.optimization.supply.demand_estimation import LOAD_PROFILES
from offgridplanner.optimization.supply.demand_estimation import calibrate_profiles
from offgridplanner.optimization.supply.demand_estimation import combine_profiles
from offgridplanner.optimization.supply.demand_estimation import (
    compute_household_demand,
)
from offgridplanner.optimization.supply.demand_estimation import compute_standard_demand
from offgridplanner.optimization.supply.demand_estimation import get_demand_timeseries
from offgridplanner.optimization.supply.demand_estimation import unpack_machinery
from offgridplanner.projects.models import Project
from offgridplanner.projects.views import populate_project_from_export
from offgridplanner.steps.models import CustomDemand
from offgridplanner.users.tests.factories import UserFactory

FLOAT_TOLERANCE = 1e-6
STRICT_FLOAT_TOLERANCE = 1e-9


# ---------- Shared fixtures (no DB) ----------


@pytest.fixture
def nodes():
    ent_detail = next(
        c.removeprefix("Enterprise_")
        for c in LOAD_PROFILES.columns
        if c.startswith("Enterprise_") and "Large Load" not in c
    )
    ps_detail = next(
        c.removeprefix("Public Service_")
        for c in LOAD_PROFILES.columns
        if c.startswith("Public Service_")
    )
    data = [
        {
            "label": "h1",
            "consumer_type": "household",
            "consumer_detail": "default",
            "is_connected": True,
            "custom_specification": "",
        },
        {
            "label": "e1",
            "consumer_type": "enterprise",
            "consumer_detail": ent_detail,
            "is_connected": True,
            "custom_specification": "",
        },
        {
            "label": "p1",
            "consumer_type": "public_service",
            "consumer_detail": ps_detail,
            "is_connected": True,
            "custom_specification": "",
        },
    ]
    n = Nodes()
    n.data = json.dumps(data)
    return n


@pytest.fixture
def custom_demand():
    return CustomDemand(very_low=0.2, low=0.2, middle=0.2, high=0.2, very_high=0.2)


@pytest.fixture
def small_profiles():
    """First 24 rows of LOAD_PROFILES to keep tests fast."""
    return LOAD_PROFILES.iloc[:24].copy()


# ---------- Integration test ----------


@pytest.fixture
def example_project_data():
    with Path(EXAMPLE_PROJECT_PATH).open() as f:
        return json.load(f)


@pytest.mark.django_db
def test_get_demand_timeseries_with_example_project(example_project_data):
    """Full pipeline from exported project through demand timeseries."""
    user = UserFactory()
    proj_id = populate_project_from_export(example_project_data, user)
    project = Project.objects.get(id=proj_id)
    real_nodes = Nodes.objects.get(project=project)
    real_custom_demand = CustomDemand.objects.get(project=project)

    time_range = range(24)
    df = get_demand_timeseries(real_nodes, real_custom_demand, time_range=time_range)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["household", "enterprise", "public_service"]
    assert len(df) == len(time_range)
    assert (df >= 0).all().all()
    assert df.sum().sum() > 0


# ---------- get_demand_timeseries ----------


class TestGetDemandTimeseries:
    def test_returns_dataframe_with_expected_columns(self, nodes, custom_demand):
        df = get_demand_timeseries(nodes, custom_demand, time_range=range(24))
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["household", "enterprise", "public_service"]

    def test_full_length_matches_load_profiles(self, nodes, custom_demand):
        df = get_demand_timeseries(nodes, custom_demand)
        assert len(df) == len(LOAD_PROFILES)

    def test_time_range_limits_row_count(self, nodes, custom_demand):
        time_range = range(48)
        df = get_demand_timeseries(nodes, custom_demand, time_range=time_range)
        assert len(df) == len(time_range)

    def test_all_values_non_negative(self, nodes, custom_demand):
        df = get_demand_timeseries(nodes, custom_demand, time_range=range(24))
        assert (df >= 0).all().all()

    def test_total_demand_is_positive(self, nodes, custom_demand):
        df = get_demand_timeseries(nodes, custom_demand, time_range=range(24))
        assert df.sum().sum() > 0


# ---------- calibrate_profiles ----------


class TestCalibrateProfiles:
    @pytest.fixture
    def base_df(self):
        return pd.DataFrame(
            {
                "household": [10.0] * 24,
                "enterprise": [5.0] * 24,
                "public_service": [2.0] * 24,
            }
        )

    @pytest.fixture
    def custom_demand_shares(self):
        return {
            "very_low": 0.2,
            "low": 0.2,
            "middle": 0.2,
            "high": 0.2,
            "very_high": 0.2,
        }

    def test_no_calibration_option_returns_unchanged(
        self, base_df, custom_demand_shares
    ):
        cd = CustomDemand(**custom_demand_shares)
        result = calibrate_profiles(base_df.copy(), cd)
        pd.testing.assert_frame_equal(result, base_df)

    def test_annual_total_consumption_scales_to_target(
        self, base_df, custom_demand_shares
    ):
        target = 999.0
        cd = CustomDemand(annual_total_consumption=target, **custom_demand_shares)
        result = calibrate_profiles(base_df.copy(), cd)
        assert abs(result.sum().sum() - target) < FLOAT_TOLERANCE

    def test_annual_peak_consumption_scales_to_target(
        self, base_df, custom_demand_shares
    ):
        target = 42.0
        cd = CustomDemand(annual_peak_consumption=target, **custom_demand_shares)
        result = calibrate_profiles(base_df.copy(), cd)
        assert abs(result.sum(axis=1).max() - target) < FLOAT_TOLERANCE

    def test_calibration_preserves_relative_column_proportions(
        self, base_df, custom_demand_shares
    ):
        cd = CustomDemand(annual_total_consumption=500.0, **custom_demand_shares)
        result = calibrate_profiles(base_df.copy(), cd)
        orig_ratio = base_df["household"].sum() / base_df["enterprise"].sum()
        result_ratio = result["household"].sum() / result["enterprise"].sum()
        assert abs(orig_ratio - result_ratio) < STRICT_FLOAT_TOLERANCE

    def test_calibration_result_is_dataframe(self, base_df, custom_demand_shares):
        cd = CustomDemand(annual_total_consumption=100.0, **custom_demand_shares)
        result = calibrate_profiles(base_df.copy(), cd)
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == list(base_df.columns)


# ---------- combine_profiles ----------


class TestCombineProfiles:
    def test_household_returns_series_of_correct_length(
        self, nodes, custom_demand, small_profiles
    ):
        result = combine_profiles(
            nodes, "household", small_profiles, custom_demand=custom_demand
        )
        assert isinstance(result, pd.Series)
        assert len(result) == len(small_profiles)

    def test_enterprise_returns_series_of_correct_length(self, nodes, small_profiles):
        result = combine_profiles(nodes, "enterprise", small_profiles)
        assert isinstance(result, pd.Series)
        assert len(result) == len(small_profiles)

    def test_public_service_returns_series_of_correct_length(
        self, nodes, small_profiles
    ):
        result = combine_profiles(nodes, "public_service", small_profiles)
        assert isinstance(result, pd.Series)
        assert len(result) == len(small_profiles)

    def test_missing_consumer_type_returns_zero_series(self, nodes, small_profiles):
        result = combine_profiles(nodes, "nonexistent_type", small_profiles)
        assert isinstance(result, pd.Series)
        assert (result == 0).all()

    def test_household_demand_non_negative(self, nodes, custom_demand, small_profiles):
        result = combine_profiles(
            nodes, "household", small_profiles, custom_demand=custom_demand
        )
        assert (result >= 0).all()


# ---------- compute_household_demand ----------


class TestComputeHouseholdDemand:
    @pytest.fixture
    def household_counts(self):
        return pd.Series({"default": 10})

    @pytest.fixture
    def demand_params(self):
        return {
            "very_low": 0.3,
            "low": 0.3,
            "middle": 0.2,
            "high": 0.1,
            "very_high": 0.1,
        }

    def test_returns_series_of_correct_length(
        self, household_counts, demand_params, small_profiles
    ):
        result = compute_household_demand(
            household_counts, demand_params, small_profiles
        )
        assert isinstance(result, pd.Series)
        assert len(result) == len(small_profiles)

    def test_values_non_negative(self, household_counts, demand_params, small_profiles):
        result = compute_household_demand(
            household_counts, demand_params, small_profiles
        )
        assert (result >= 0).all()

    def test_scales_linearly_with_household_count(self, demand_params, small_profiles):
        counts_10 = pd.Series({"default": 10})
        counts_20 = pd.Series({"default": 20})
        result_10 = compute_household_demand(counts_10, demand_params, small_profiles)
        result_20 = compute_household_demand(counts_20, demand_params, small_profiles)
        pd.testing.assert_series_equal(result_20, result_10 * 2)

    def test_zero_households_returns_zero_series(self, demand_params, small_profiles):
        counts = pd.Series({"default": 0})
        result = compute_household_demand(counts, demand_params, small_profiles)
        assert (result == 0).all()

    def test_single_tier_matches_profile_times_count(self, small_profiles):
        counts = pd.Series({"default": 5})
        params = {
            "very_low": 1.0,
            "low": 0.0,
            "middle": 0.0,
            "high": 0.0,
            "very_high": 0.0,
        }
        result = compute_household_demand(counts, params, small_profiles)
        expected_col = "Household_Distribution_Based_Very Low Consumption"
        expected = small_profiles[expected_col] * 5
        pd.testing.assert_series_equal(result, expected, check_names=False)


# ---------- compute_standard_demand ----------


class TestComputeStandardDemand:
    def _first_detail(self, prefix, exclude_prefix=None):
        """Return (consumer_detail, full_column_name) for first matching load profile column."""
        cols = [
            c
            for c in LOAD_PROFILES.columns
            if c.startswith(f"{prefix}_")
            and (exclude_prefix is None or exclude_prefix not in c)
        ]
        assert cols, f"No columns found with prefix '{prefix}'"
        return cols[0].removeprefix(f"{prefix}_"), cols[0]

    def test_enterprise_returns_correct_series(self, small_profiles):
        detail, full_col = self._first_detail("Enterprise", exclude_prefix="Large Load")
        counts = pd.Series({detail: 3})
        result = compute_standard_demand("enterprise", counts, small_profiles)
        assert isinstance(result, pd.Series)
        assert len(result) == len(small_profiles)
        pd.testing.assert_series_equal(
            result, small_profiles[full_col] * 3, check_names=False
        )

    def test_public_service_returns_correct_series(self, small_profiles):
        detail, full_col = self._first_detail("Public Service")
        counts = pd.Series({detail: 2})
        result = compute_standard_demand("public_service", counts, small_profiles)
        assert isinstance(result, pd.Series)
        pd.testing.assert_series_equal(
            result, small_profiles[full_col] * 2, check_names=False
        )

    def test_machinery_returns_correct_series(self, small_profiles):
        large_load_cols = [c for c in LOAD_PROFILES.columns if "Large Load_" in c]
        assert large_load_cols, "No large load columns in load profiles"
        detail = large_load_cols[0].split("Large Load_")[1]
        counts = pd.Series({detail: 1})
        result = compute_standard_demand("machinery", counts, small_profiles)
        assert isinstance(result, pd.Series)
        assert len(result) == len(small_profiles)


# ---------- unpack_machinery ----------


class TestUnpackMachinery:
    def test_extracts_single_machine(self):
        df = pd.DataFrame({"custom_specification": ["1 x Welder (5.25kW)"]})
        result = unpack_machinery(df)
        assert isinstance(result, pd.Series)
        assert result["Welder"] == 1

    def test_extracts_multiple_machines_from_one_row(self):
        df = pd.DataFrame(
            {"custom_specification": ["2 x Milling Machine (7.5kW);1 x Drill (0.4kW)"]}
        )
        result = unpack_machinery(df)
        assert result["Milling Machine"] == 2  # noqa: PLR2004
        assert result["Drill"] == 1

    def test_sums_duplicate_machine_types_across_rows(self):
        df = pd.DataFrame(
            {
                "custom_specification": [
                    "1 x Welder (5.25kW)",
                    "2 x Welder (5.25kW)",
                ]
            }
        )
        result = unpack_machinery(df)
        assert result["Welder"] == 3  # noqa: PLR2004

    def test_sums_duplicate_machine_types_within_one_row(self):
        df = pd.DataFrame(
            {"custom_specification": ["3 x Sawmill (2.25kW);2 x Sawmill (2.25kW)"]}
        )
        result = unpack_machinery(df)
        assert result["Sawmill"] == 5  # noqa: PLR2004

    def test_count_is_integer_type(self):
        df = pd.DataFrame({"custom_specification": ["4 x Grinder (5.2kW)"]})
        result = unpack_machinery(df)
        assert pd.api.types.is_integer_dtype(result)
