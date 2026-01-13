from io import StringIO

import pandas as pd
from django.db import models

from offgridplanner.projects.models import Project


class BaseJsonData(models.Model):
    # An abstract class for all models that only have a data JSONField
    project = models.OneToOneField(Project, on_delete=models.CASCADE, null=True)
    data = models.JSONField(null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.__class__.__name__} {self.id}: Project {self.project.name}"

    @property
    def df(self):
        return pd.read_json(StringIO(self.data)) if self.data else None


class Nodes(BaseJsonData):
    def filter_consumers(self, consumer_type):
        """
        Parameters:
            consumer_type (str): One of "household", "enterprise", "public_service"
        """
        nodes = self.df
        consumer_type_df = nodes[
            (nodes["consumer_type"] == consumer_type) & (nodes["is_connected"] == True)  # noqa:E712
        ]
        return consumer_type_df

    @property
    def counts(self):
        counts = self.df.groupby(["consumer_type", "consumer_detail"]).size()
        return counts

    @property
    def have_custom_machinery(self):
        enterprises = self.df[self.df.consumer_type == "enterprise"]
        machinery = (
            enterprises.groupby(["consumer_type", "consumer_detail"])
            .agg({"custom_specification": ";".join})
            .custom_specification.loc["enterprise"]
        )
        machinery.replace(";", "")
        return bool(not machinery.eq("").all())


class Links(BaseJsonData):
    pass


class Roads(BaseJsonData):
    pass


class WeatherData(models.Model):
    dt = models.DateTimeField()
    lat = models.FloatField()
    lon = models.FloatField()
    wind_speed = models.FloatField(null=True, blank=True)
    temp_air = models.FloatField(null=True, blank=True)
    ghi = models.FloatField(null=True, blank=True)
    dni = models.FloatField(null=True, blank=True)
    dhi = models.FloatField(null=True, blank=True)

    # class Meta:
    #     unique_together = ("dt", "lat", "lon")

    def __str__(self):
        return f"WeatherData({self.dt}, {self.lat}, {self.lon})"


class Simulation(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, null=True)
    token_grid = models.CharField(max_length=80, blank=True, default="")
    token_supply = models.CharField(max_length=80, blank=True, default="")
    status_grid = models.CharField(max_length=25, default="not yet started")
    status_supply = models.CharField(max_length=25, default="not yet started")

    def __str__(self):
        return f"Simulation {self.id}: Project {self.project.name}"


class Results(models.Model):
    # TODO potentially remove redundant fields that can just be calculated on the fly (e.g. upfront investment)
    simulation = models.OneToOneField(Simulation, on_delete=models.CASCADE, null=True)
    n_consumers = models.PositiveSmallIntegerField(null=True, blank=True)
    n_shs_consumers = models.PositiveSmallIntegerField(null=True, blank=True)
    n_poles = models.PositiveSmallIntegerField(null=True, blank=True)
    n_distribution_links = models.PositiveSmallIntegerField(null=True, blank=True)
    n_connection_links = models.PositiveSmallIntegerField(null=True, blank=True)
    length_distribution_cable = models.PositiveSmallIntegerField(null=True, blank=True)
    average_length_distribution_cable = models.FloatField(null=True, blank=True)
    length_connection_cable = models.PositiveSmallIntegerField(null=True, blank=True)
    average_length_connection_cable = models.FloatField(null=True, blank=True)
    cost_grid = models.FloatField(null=True, blank=True)
    cost_shs = models.FloatField(null=True, blank=True)
    lcoe = models.FloatField(null=True, blank=True)
    lcoe_share_grid = models.FloatField(null=True, blank=True)
    lcoe_share_supply = models.FloatField(null=True, blank=True)
    res = models.FloatField(null=True, blank=True)
    shortage_total = models.FloatField(null=True, blank=True)
    surplus_rate = models.FloatField(null=True, blank=True)
    cost_renewable_assets = models.FloatField(null=True, blank=True)
    cost_non_renewable_assets = models.FloatField(null=True, blank=True)
    cost_fuel = models.FloatField(null=True, blank=True)
    pv_capacity = models.FloatField(null=True, blank=True)
    battery_capacity = models.FloatField(null=True, blank=True)
    inverter_capacity = models.FloatField(null=True, blank=True)
    rectifier_capacity = models.FloatField(null=True, blank=True)
    diesel_genset_capacity = models.FloatField(null=True, blank=True)
    peak_demand = models.FloatField(null=True, blank=True)
    surplus = models.FloatField(null=True, blank=True)
    fuel_to_diesel_genset = models.FloatField(null=True, blank=True)
    diesel_genset_to_rectifier = models.FloatField(null=True, blank=True)
    diesel_genset_to_demand = models.FloatField(null=True, blank=True)
    rectifier_to_dc_bus = models.FloatField(null=True, blank=True)
    pv_to_dc_bus = models.FloatField(null=True, blank=True)
    battery_to_dc_bus = models.FloatField(null=True, blank=True)
    dc_bus_to_battery = models.FloatField(null=True, blank=True)
    dc_bus_to_inverter = models.FloatField(null=True, blank=True)
    dc_bus_to_surplus = models.FloatField(null=True, blank=True)
    inverter_to_demand = models.FloatField(null=True, blank=True)
    time_grid_design = models.FloatField(null=True, blank=True)
    time_energy_system_design = models.FloatField(null=True, blank=True)
    time = models.FloatField(null=True, blank=True)
    co2_savings = models.FloatField(null=True, blank=True)
    max_voltage_drop = models.FloatField(null=True, blank=True)
    infeasible = models.PositiveSmallIntegerField(null=True, blank=True)
    average_annual_demand_per_consumer = models.FloatField(null=True, blank=True)
    total_annual_consumption = models.FloatField(null=True, blank=True)
    upfront_invest_grid = models.FloatField(null=True, blank=True)
    upfront_invest_diesel_genset = models.FloatField(null=True, blank=True)
    upfront_invest_inverter = models.FloatField(null=True, blank=True)
    upfront_invest_rectifier = models.FloatField(null=True, blank=True)
    upfront_invest_battery = models.FloatField(null=True, blank=True)
    upfront_invest_pv = models.FloatField(null=True, blank=True)
    upfront_invest_total = models.FloatField(null=True, blank=True)
    co2_emissions = models.FloatField(null=True, blank=True)
    fuel_consumption = models.FloatField(null=True, blank=True)
    base_load = models.FloatField(null=True, blank=True)
    max_shortage = models.FloatField(null=True, blank=True)
    epc_total = models.FloatField(null=True, blank=True)
    epc_pv = models.FloatField(null=True, blank=True)
    epc_diesel_genset = models.FloatField(null=True, blank=True)
    epc_inverter = models.FloatField(null=True, blank=True)
    epc_rectifier = models.FloatField(null=True, blank=True)
    epc_battery = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Results {self.id}: Project {self.simulation.project.name}"

    def process_shared_results(self):
        """
        Processes KPIs that are computed combining grid and supply results (other KPIs are updated within the
        GridProcessor and SupplyProcessor classes)
        """
        self.lcoe_share_supply = (
            (self.epc_total - self.cost_grid) / self.epc_total * 100
        )
        self.lcoe_share_grid = 100 - self.lcoe_share_supply
        assets = ["grid", "diesel_genset", "inverter", "rectifier", "battery", "pv"]
        self.upfront_invest_total = sum(
            [getattr(self, f"upfront_invest_{key}") for key in assets]
        )


# TODO check what is saved in these models and potentially restructure in db
class Emissions(BaseJsonData):
    pass


class DurationCurve(BaseJsonData):
    pass


class EnergyFlow(BaseJsonData):
    pass


class DemandCoverage(BaseJsonData):
    pass
