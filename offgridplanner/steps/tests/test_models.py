import json
from pathlib import Path

import pytest

from config.settings.base import EXAMPLE_PROJECT_PATH
from offgridplanner.projects.models import Project
from offgridplanner.projects.views import populate_project_from_export
from offgridplanner.steps.models import CustomDemand
from offgridplanner.steps.models import EnergySystemDesign
from offgridplanner.steps.models import GridDesign
from offgridplanner.users.tests.factories import UserFactory

STRICT_FLOAT_TOLERANCE = 1e-9


@pytest.fixture
def example_project_data():
    with Path(EXAMPLE_PROJECT_PATH).open() as f:
        return json.load(f)


@pytest.fixture
def project(db, example_project_data):
    user = UserFactory()
    proj_id = populate_project_from_export(example_project_data, user)
    return Project.objects.get(id=proj_id)


# ---------- TestCustomDemand ----------


class TestCustomDemand:
    def test_calibration_option_none_when_both_none(self):
        cd = CustomDemand(very_low=0.2, low=0.2, middle=0.2, high=0.2, very_high=0.2)
        assert cd.calibration_option is None

    def test_calibration_option_returns_annual_total(self):
        cd = CustomDemand(annual_total_consumption=1000.0)
        assert cd.calibration_option == "annual_total_consumption"

    def test_calibration_option_returns_annual_peak_when_total_none(self):
        cd = CustomDemand(annual_peak_consumption=50.0)
        assert cd.calibration_option == "annual_peak_consumption"

    def test_calibration_option_total_takes_precedence_over_peak(self):
        cd = CustomDemand(annual_total_consumption=1000.0, annual_peak_consumption=50.0)
        assert cd.calibration_option == "annual_total_consumption"

    def test_shares_tiers_has_five_entries(self):
        cd = CustomDemand()
        assert len(cd.shares_tiers) == 5  # noqa: PLR2004
        assert set(cd.shares_tiers) == {
            "very_low",
            "low",
            "middle",
            "high",
            "very_high",
        }

    def test_get_shares_dict_returns_field_values(self):
        cd = CustomDemand(very_low=0.1, low=0.2, middle=0.3, high=0.25, very_high=0.15)
        result = cd.get_shares_dict()
        assert result["very_low"] == 0.1  # noqa: PLR2004
        assert result["high"] == 0.25  # noqa: PLR2004

    def test_get_shares_dict_as_percentage_multiplies_by_100(self):
        cd = CustomDemand(very_low=0.1, low=0.2, middle=0.3, high=0.25, very_high=0.15)
        result = cd.get_shares_dict(as_percentage=True)
        assert abs(result["very_low"] - 10.0) < STRICT_FLOAT_TOLERANCE
        assert abs(result["middle"] - 30.0) < STRICT_FLOAT_TOLERANCE


# ---------- TestGridDesignToNestedDict ----------


@pytest.mark.django_db
class TestGridDesignToNestedDict:
    @pytest.fixture
    def grid_design(self, project):
        return GridDesign.objects.get(project=project)

    def test_returns_dict(self, grid_design):
        assert isinstance(grid_design.to_nested_dict(), dict)

    def test_distribution_cable_key_present(self, grid_design):
        assert "distribution_cable" in grid_design.to_nested_dict()

    def test_pole_key_present(self, grid_design):
        assert "pole" in grid_design.to_nested_dict()

    def test_mg_key_present(self, grid_design):
        assert "mg" in grid_design.to_nested_dict()

    def test_nested_lifetime_matches_model_field(self, grid_design):
        result = grid_design.to_nested_dict()
        assert (
            result["distribution_cable"]["lifetime"]
            == grid_design.distribution_cable_lifetime
        )

    def test_nested_capex_matches_model_field(self, grid_design):
        result = grid_design.to_nested_dict()
        assert result["pole"]["capex"] == grid_design.pole_capex


# ---------- TestEnergySystemDesignToNestedDict ----------


@pytest.mark.django_db
class TestEnergySystemDesignToNestedDict:
    @pytest.fixture
    def energy_system_design(self, project):
        return EnergySystemDesign.objects.get(project=project)

    def test_returns_dict(self, energy_system_design):
        assert isinstance(energy_system_design.to_nested_dict(), dict)

    def test_battery_key_present(self, energy_system_design):
        assert "battery" in energy_system_design.to_nested_dict()

    def test_diesel_genset_key_present(self, energy_system_design):
        assert "diesel_genset" in energy_system_design.to_nested_dict()

    def test_settings_nested_under_component(self, energy_system_design):
        assert "settings" in energy_system_design.to_nested_dict()["battery"]

    def test_parameters_nested_under_component(self, energy_system_design):
        assert "parameters" in energy_system_design.to_nested_dict()["battery"]

    def test_is_selected_matches_model_field(self, energy_system_design):
        result = energy_system_design.to_nested_dict()
        assert (
            result["battery"]["settings"]["is_selected"]
            == energy_system_design.battery_settings_is_selected
        )
