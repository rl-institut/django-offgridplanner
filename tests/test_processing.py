import types

import numpy as np

from offgridplanner.optimization.processing import OptimizationDataHandler
from offgridplanner.optimization.processing import SupplyProcessor

FLOAT_TOLERANCE = 1e-6
CO2_FACTOR_SMALL = 1.580
CO2_FACTOR_MEDIUM = 0.883
CO2_FACTOR_LARGE = 0.699
SMALL_GENSET_MAX_KW = 60
MEDIUM_GENSET_MAX_KW = 300


class _HandlerStub:
    """Reuses pure OptimizationDataHandler methods without DB access."""

    annualize = OptimizationDataHandler.annualize
    capex_multi_investment = OptimizationDataHandler.capex_multi_investment
    epc = OptimizationDataHandler.epc

    def __init__(self, wacc=0.1, lifetime=20, n_days=365, tax=0.0):
        self.wacc = wacc
        self.project_lifetime = float(lifetime)
        self.tax = tax
        self.crf = (wacc * (1 + wacc) ** lifetime) / ((1 + wacc) ** lifetime - 1)
        self.project = types.SimpleNamespace(n_days=n_days)


class _SupplyStub(_HandlerStub):
    """Extends _HandlerStub with the sequences needed for emission calculations."""

    def __init__(self, genset_capacity, n_hours=24, **kwargs):
        super().__init__(**kwargs)
        self.capacities = {"diesel_genset": genset_capacity}
        self.sequences = {
            "genset": np.ones(n_hours) * 5.0,
            "demand": np.ones(n_hours) * 10.0,
        }


# ---------- SupplyProcessor.to_kwh ----------


class TestToKwh:
    def test_converts_watts_to_kilowatts(self):
        assert SupplyProcessor.to_kwh(1000) == 1.0

    def test_zero_returns_zero(self):
        assert SupplyProcessor.to_kwh(0) == 0.0

    def test_none_returns_zero(self):
        assert SupplyProcessor.to_kwh(None) == 0

    def test_fractional_value(self):
        assert abs(SupplyProcessor.to_kwh(500) - 0.5) < FLOAT_TOLERANCE


# ---------- OptimizationDataHandler.annualize ----------


class TestAnnualize:
    def test_annualizes_from_full_year(self):
        obj = _HandlerStub(n_days=365)
        result = OptimizationDataHandler.annualize(obj, 365.0)
        assert abs(result - 365.0) < FLOAT_TOLERANCE

    def test_annualizes_from_single_day(self):
        obj = _HandlerStub(n_days=1)
        result = OptimizationDataHandler.annualize(obj, 10.0)
        assert abs(result - 10.0 * 365) < FLOAT_TOLERANCE

    def test_none_returns_zero(self):
        obj = _HandlerStub()
        assert OptimizationDataHandler.annualize(obj, None) == 0

    def test_scales_linearly_with_value(self):
        obj = _HandlerStub(n_days=365)
        r1 = OptimizationDataHandler.annualize(obj, 100.0)
        r2 = OptimizationDataHandler.annualize(obj, 200.0)
        assert abs(r2 - r1 * 2) < FLOAT_TOLERANCE


# ---------- OptimizationDataHandler.capex_multi_investment ----------


class TestCapexMultiInvestment:
    def test_same_lifetime_returns_capex(self):
        obj = _HandlerStub(wacc=0.1, lifetime=20)
        result = OptimizationDataHandler.capex_multi_investment(obj, 1000.0, 20.0)
        assert abs(result - 1000.0) < FLOAT_TOLERANCE

    def test_shorter_component_lifetime_increases_capex(self):
        obj = _HandlerStub(wacc=0.1, lifetime=20)
        result_same = OptimizationDataHandler.capex_multi_investment(obj, 1000.0, 20.0)
        result_short = OptimizationDataHandler.capex_multi_investment(obj, 1000.0, 10.0)
        assert result_short > result_same

    def test_returns_float(self):
        obj = _HandlerStub()
        result = OptimizationDataHandler.capex_multi_investment(obj, 500.0, 10.0)
        assert isinstance(result, float)

    def test_zero_capex_returns_zero(self):
        obj = _HandlerStub()
        result = OptimizationDataHandler.capex_multi_investment(obj, 0.0, 10.0)
        assert abs(result) < FLOAT_TOLERANCE

    def test_higher_wacc_reduces_equivalent_capex(self):
        obj_low = _HandlerStub(wacc=0.05, lifetime=20)
        obj_high = _HandlerStub(wacc=0.20, lifetime=20)
        result_low = OptimizationDataHandler.capex_multi_investment(
            obj_low, 1000.0, 10.0
        )
        result_high = OptimizationDataHandler.capex_multi_investment(
            obj_high, 1000.0, 10.0
        )
        # Higher discount rate → replacement cost worth less → lower equivalent capex
        assert result_high < result_low


# ---------- OptimizationDataHandler.epc ----------


class TestEpc:
    def test_returns_positive_for_positive_capex(self):
        obj = _HandlerStub(wacc=0.1, lifetime=20)
        result = OptimizationDataHandler.epc(obj, capex=1000.0, opex=0.0, lifetime=20.0)
        assert result > 0

    def test_opex_adds_to_epc(self):
        obj = _HandlerStub(wacc=0.1, lifetime=20)
        result_no_opex = OptimizationDataHandler.epc(obj, 1000.0, 0.0, 20.0)
        result_with_opex = OptimizationDataHandler.epc(obj, 1000.0, 50.0, 20.0)
        assert abs(result_with_opex - result_no_opex - 50.0) < FLOAT_TOLERANCE

    def test_zero_capex_and_opex_returns_zero(self):
        obj = _HandlerStub()
        result = OptimizationDataHandler.epc(obj, 0.0, 0.0, 20.0)
        assert abs(result) < FLOAT_TOLERANCE


# ---------- SupplyProcessor._calculate_emissions ----------


class TestCalculateEmissions:
    def test_small_genset_uses_small_factor(self):
        obj = _SupplyStub(genset_capacity=SMALL_GENSET_MAX_KW - 1)
        SupplyProcessor._calculate_emissions(obj)  # noqa: SLF001
        assert obj.co2_emission_factor == CO2_FACTOR_SMALL

    def test_medium_genset_uses_medium_factor(self):
        obj = _SupplyStub(genset_capacity=SMALL_GENSET_MAX_KW + 1)
        SupplyProcessor._calculate_emissions(obj)  # noqa: SLF001
        assert obj.co2_emission_factor == CO2_FACTOR_MEDIUM

    def test_large_genset_uses_large_factor(self):
        obj = _SupplyStub(genset_capacity=MEDIUM_GENSET_MAX_KW + 1)
        SupplyProcessor._calculate_emissions(obj)  # noqa: SLF001
        assert obj.co2_emission_factor == CO2_FACTOR_LARGE

    def test_emissions_df_has_two_columns(self):
        obj = _SupplyStub(genset_capacity=10.0)
        SupplyProcessor._calculate_emissions(obj)  # noqa: SLF001
        assert "non_renewable_electricity_production" in obj.emissions_df.columns
        assert "hybrid_electricity_production" in obj.emissions_df.columns

    def test_co2_savings_non_negative(self):
        obj = _SupplyStub(genset_capacity=10.0)
        SupplyProcessor._calculate_emissions(obj)  # noqa: SLF001
        assert obj.co2_savings >= 0

    def test_full_renewable_has_max_co2_savings(self):
        # When genset produces nothing, savings equal non-renewable baseline
        n_hours = 24
        obj = _SupplyStub(genset_capacity=10.0, n_hours=n_hours)
        obj.sequences["genset"] = np.zeros(n_hours)
        SupplyProcessor._calculate_emissions(obj)  # noqa: SLF001
        assert (
            obj.co2_savings
            == obj.emissions_df["non_renewable_electricity_production"].max()
        )
