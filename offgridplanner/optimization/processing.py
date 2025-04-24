# Pre- and post-processing for the grid and supply optimization
import json
from io import StringIO

import numpy as np
import pandas as pd
from django.shortcuts import get_object_or_404

from offgridplanner.optimization.models import DemandCoverage
from offgridplanner.optimization.models import DurationCurve
from offgridplanner.optimization.models import Emissions
from offgridplanner.optimization.models import EnergyFlow
from offgridplanner.optimization.models import Links
from offgridplanner.optimization.models import Nodes
from offgridplanner.optimization.models import Results
from offgridplanner.optimization.supply.demand_estimation import get_demand_timeseries
from offgridplanner.optimization.supply.solar_potential import (
    get_dc_feed_in_sync_db_query,
)
from offgridplanner.projects.models import Project


def json_to_db_model(obj, data):
    """
    Updates the data attribute of a BaseJsonData model
    """
    obj.data = data
    obj.save()


class OptimizationDataHandler:
    def __init__(self, proj_id):
        self.project = get_object_or_404(Project, id=proj_id)
        self.options = self.project.options
        self.energy_system_dict = self.project.energysystemdesign.to_nested_dict()
        self.supply_components = self.energy_system_dict.keys()
        self.grid_design_dict = self.project.griddesign.to_nested_dict()
        self.grid_components = self.grid_design_dict.keys()
        self.demand = self.collect_project_demand()
        self.demand_full_year = self.demand * 365 / self.project.n_days
        self.tax = 0
        self.wacc = self.project.interest_rate / 100
        self.project_lifetime = self.project.lifetime
        self.crf = (self.wacc * (1 + self.wacc) ** self.project_lifetime) / (
            (1 + self.wacc) ** self.project_lifetime - 1
        )

        self.energy_system_dict = self.add_epc_to_dict(
            self.energy_system_dict,
            ["battery", "diesel_genset", "inverter", "rectifier", "pv"],
        )

        self.grid_design_dict = self.add_epc_to_dict(
            self.grid_design_dict, ["distribution_cable", "connection_cable", "pole"]
        )
        self.grid_design_dict["mg"]["epc"] = self.epc(
            self.grid_design_dict["mg"]["connection_cost"], 0, self.project.lifetime
        )

    def annualize(self, value):
        return value / self.project.n_days * 365 if value is not None else 0

    def add_epc_to_dict(self, nested_dict, components):
        """
        Replaces the parameters "capex", "opex" and "lifetime" inside a nested dictionary with "epc" for all components
        specified in components.
        Parameters:
            nested_dict (dict): Nested dictionary from a NestedModel object
            components (list): List of strings with the component names
        Returns:
            dict: Edited dict with the epc values
        """
        if set(components).issubset(self.supply_components):
            for component in components:
                capex = nested_dict[component]["parameters"]["capex"]
                opex = nested_dict[component]["parameters"]["opex"]
                lifetime = nested_dict[component]["parameters"]["lifetime"]
                # add periodical costs to dict
                nested_dict[component]["parameters"]["epc"] = self.epc(
                    capex, opex, lifetime
                )
                # delete parameters that are no longer needed for the optimization (reduce size of the json)
                # del nested_dict[component]["parameters"]["capex"]
                # del nested_dict[component]["parameters"]["opex"]
                # del nested_dict[component]["parameters"]["lifetime"]

        elif set(components).issubset(self.grid_components):
            for component in components:
                capex = nested_dict[component]["capex"]
                opex = 0
                lifetime = nested_dict[component]["lifetime"]
                # add periodical costs to dict
                nested_dict[component]["epc"] = self.epc(capex, opex, lifetime)
                # delete parameters that are no longer needed for the optimization (reduce size of the json)
                # del nested_dict[component]["lifetime"]

        else:
            err = "Components found neither in grid nor energy system models"
            raise ValueError(err)

        return nested_dict

    def epc(self, capex, opex, lifetime):
        epc = self.annualize(
            self.crf
            * self.capex_multi_investment(
                capex_0=capex,
                component_lifetime=lifetime,
            )
            + opex,
        )

        return epc

    def capex_multi_investment(self, capex_0, component_lifetime):
        """
        Calculates the equivalent CAPEX for components
        with lifetime less than the self.project lifetime.

        """
        # convert the string type into the float type for both inputs
        capex_0 = float(capex_0)
        component_lifetime = float(component_lifetime)
        if self.project_lifetime == component_lifetime:
            number_of_investments = 1
        else:
            number_of_investments = int(
                round(self.project_lifetime / component_lifetime + 0.5),
            )
        first_time_investment = capex_0 * (1 + self.tax)
        capex = first_time_investment
        for count_of_replacements in range(1, number_of_investments):
            if count_of_replacements * component_lifetime != self.project_lifetime:
                capex += first_time_investment / (
                    (1 + self.wacc) ** (count_of_replacements * component_lifetime)
                )
        # Subtraction of component value at end of life with last replacement (= number_of_investments - 1)
        # This part calculates the salvage costs
        if number_of_investments * component_lifetime > self.project_lifetime:
            last_investment = first_time_investment / (
                (1 + self.wacc) ** ((number_of_investments - 1) * component_lifetime)
            )
            linear_depreciation_last_investment = last_investment / component_lifetime
            capex = capex - linear_depreciation_last_investment * (
                number_of_investments * component_lifetime - self.project_lifetime
            ) / ((1 + self.wacc) ** self.project_lifetime)
        return capex

    def collect_project_demand(self):
        """
        Check if the user has ticked the demand estimation box. If so, calculate the demand from the project nodes,
        else get the demand from the uploaded timeseries
        Returns:
            pd.DataFrame
        """
        if self.options.do_demand_estimation:
            demand_full_year = get_demand_timeseries(
                self.project.nodes, self.project.customdemand
            ).sum(axis=1)

            demand = demand_full_year.iloc[: (self.project.n_days * 24)]
        else:
            uploaded_data = self.project.customdemand.uploaded_data
            demand = pd.read_json(StringIO(uploaded_data))["demand"]
            # # TODO error is thrown for annual total consumption if full year demand is not defined - tbd fix
            # if self.n_days == 365:
            #     self.demand_full_year = self.demand
        return demand


class PreProcessor(OptimizationDataHandler):
    """
    Replaces the previous class BaseOptimizer by calculating values needed for the optimization. Used to create
    jsons sent to the actual optimizer / simulation server
    """

    def __init__(self, proj_id):
        super().__init__(proj_id)

    def get_site_coordinates(self):
        # TODO do currently default coords get set if the user uploads a timeseries instead of selecting consumers?
        #  There should be an input about the project site instead
        default_coords = (9.055158, 7.497112)
        nodes_qs = Nodes.objects.filter(project=self.project)
        if nodes_qs.exists():
            nodes = nodes_qs.get().df
            if not nodes[nodes["consumer_type"] == "power_house"].empty:
                lat, lon = nodes[nodes["consumer_type"] == "power_house"][
                    "latitude",
                    "longitude",
                ].to_list()
            else:
                lat, lon = nodes[["latitude", "longitude"]].mean().to_list()
        else:
            lat, lon = default_coords

        return lat, lon

    def collect_supply_opt_json_data(self):
        """
        Dumps the necessary data for the supply optimization into a single json object to be sent to the simulation server
        Returns:
             json: Json data containing oemof component parameters and necessary timeseries
        """
        lat, lon = self.get_site_coordinates()
        # TODO fix date to actual start_date
        # self.start_datetime = pd.to_datetime(self.project_dict["start_date"]).to_pydatetime()
        # start_datetime hardcoded as only 2022 pv and demand data is available
        start_datetime = pd.to_datetime("2022").to_pydatetime()
        dt_index = pd.date_range(
            start_datetime,
            start_datetime + pd.to_timedelta(self.project.n_days, unit="D"),
            freq="h",
            inclusive="left",
        )

        solar_potential = get_dc_feed_in_sync_db_query(
            lat,
            lon,
            dt_index,
        )

        sequences = {
            "index": self.demand.index.strftime("%Y-%m-%dT%H:%M:%S").tolist(),
            "demand": self.demand.to_numpy().tolist(),
            "solar_potential": solar_potential.to_numpy().tolist(),
        }
        energy_system_design = self.energy_system_dict

        # calculate periodical costs of components out of input capex, opex and lifetime

        supply_opt_json = {
            "sequences": sequences,
            "energy_system_design": energy_system_design,
        }

        return supply_opt_json

    def collect_grid_opt_json_data(self):
        # calculate periodical costs of components out of input capex, opex and lifetime

        grid_opt_json = {
            "nodes": self.project.nodes.df.to_json(),
            "grid_design": self.grid_design_dict,
            "yearly_demand": self.demand.sum(),
        }
        return grid_opt_json


class GridProcessor(OptimizationDataHandler):
    def __init__(self, results_json, proj_id):
        super().__init__(proj_id)
        self.results_obj, _ = Results.objects.get_or_create(
            simulation=self.project.simulation
        )
        self.nodes_obj, _ = Nodes.objects.get_or_create(project=self.project)
        self.links_obj, _ = Links.objects.get_or_create(project=self.project)
        self.grid_results = results_json
        self.nodes_df = pd.read_json(self.grid_results["nodes"])
        self.links_df = pd.read_json(self.grid_results["links"])

    def grid_results_to_db(self):
        # read the nodes and links data and save to the database
        json_to_db_model(self.nodes_obj, self.nodes_df.to_json())
        json_to_db_model(self.links_obj, self.links_df.to_json())
        # compute the other results and save to the results object
        results = self.results_obj
        n_consumers = len(self.nodes_df[self.nodes_df["node_type"] == "consumer"])
        n_shs_consumers = len(self.nodes_df[self.nodes_df["is_connected"] == False])  # noqa:E712
        n_poles = len(
            self.nodes_df[
                (self.nodes_df["node_type"] == "pole")
                | (self.nodes_df["node_type"] == "power-house")
            ]
        )
        n_mg_consumers = n_consumers - n_shs_consumers
        results.n_poles = n_poles
        results.n_consumers = n_consumers
        results.n_shs_consumers = n_shs_consumers

        results.length_distribution_cable = int(
            self.links_df[self.links_df.link_type == "distribution"]["length"].sum(),
        )

        results.length_connection_cable = int(
            self.links_df[self.links_df.link_type == "connection"]["length"].sum(),
        )
        results.cost_grid = (
            int(self.grid_cost(n_poles, n_mg_consumers, len(self.links_df)))
            if len(self.links_df) > 0
            else 0
        )
        results.cost_shs = 0
        # TODO this is not really necessary with the simulation server
        results.time_grid_design = 0
        results.n_distribution_links = int(
            self.links_df[self.links_df["link_type"] == "distribution"].shape[0],
        )
        results.n_connection_links = int(
            self.links_df[self.links_df["link_type"] == "connection"].shape[0],
        )
        length_dist_cable = self.links_df[self.links_df["link_type"] == "distribution"][
            "length"
        ].sum()
        length_conn_cable = self.links_df[self.links_df["link_type"] == "connection"][
            "length"
        ].sum()
        num_households = len(
            self.nodes_df[
                (self.nodes_df["consumer_type"] == "household")
                & (self.nodes_df["is_connected"] == True)  # noqa:E712
            ].index,
        )
        results.upfront_invest_grid = (
            results.n_poles * self.grid_design_dict["pole"]["capex"]
            + length_dist_cable * self.grid_design_dict["distribution_cable"]["capex"]
            + length_conn_cable * self.grid_design_dict["connection_cable"]["capex"]
            + num_households * self.grid_design_dict["mg"]["connection_cost"]
        )

        results.save()

    def total_length_distribution_cable(self):
        """
        Calculates the total length of all cables connecting only poles in the grid.

        Returns
        ------
        type: float
            the total length of the distribution cable in the grid
        """
        return self.links_df.length[self.links_df.link_type == "distribution"].sum()

    def total_length_connection_cable(self):
        """
        Calculates the total length of all cables between each pole and
        consumers.

        Returns
        ------
        type: float
            total length of the connection cable in the grid.
        """
        return self.links_df.length[self.links_df.link_type == "connection"].sum()

    def grid_cost(self, n_poles, n_mg_consumers, n_links):
        """
        Computes the cost of the grid taking into account the number
        of nodes, their types (consumer or poles) and the length of
        different types of cables between nodes.

        Return
        ------
        cost of the grid
        """

        # if there is no poles in the grid, or there is no link,
        # the function returns an infinite value
        if (n_poles == 0) or (n_links == 0):
            return np.inf

        # calculate the total length of the cable used between poles [m]
        total_length_distribution_cable = self.total_length_distribution_cable()

        # calculate the total length of the `connection` cable between poles and consumers
        total_length_connection_cable = self.total_length_connection_cable()
        grid_cost = (
            n_poles * self.grid_design_dict["pole"]["epc"]
            + n_mg_consumers * self.grid_design_dict["mg"]["epc"]
            + total_length_connection_cable
            * self.grid_design_dict["connection_cable"]["epc"]
            + total_length_distribution_cable
            * self.grid_design_dict["distribution_cable"]["epc"]
        )

        return np.around(grid_cost, decimals=2)


class SupplyProcessor(OptimizationDataHandler):
    def __init__(self, results_json, proj_id):
        super().__init__(proj_id)
        self.results_obj, _ = Results.objects.get_or_create(
            simulation=self.project.simulation
        )
        self.supply_results = results_json
        nodes_df = self.project.nodes.df
        self.num_households = len(
            nodes_df[
                (nodes_df["consumer_type"] == "household")
                & (nodes_df["is_connected"] == True)  # noqa:E712
            ]
        )

    def _process_supply_optimization_results(self):
        # nodes = [
        #     "pv",
        #     "fuel_source",
        #     "diesel_genset",
        #     "inverter",
        #     "rectifier",
        #     "battery",
        #     "electricity_demand",
        #     "surplus",
        #     "shortage",
        # ]

        # TODO replace this with json response results and adapt formatting
        results = self.supply_results
        #  SEQUENCES (DYNAMIC)
        # self.sequences_demand = results["electricity_demand"]["sequences"][
        #     (("electricity_ac", "electricity_demand"), "flow")
        # ]

        self.sequences = {
            "pv": {"comp": "pv", "key": "pv__electricity_dc"},
            "genset": {
                "comp": "diesel_genset",
                "key": "diesel_genset__electricity_ac",
            },
            "battery_charge": {
                "comp": "battery",
                "key": "electricity_dc__battery",
            },
            "battery_discharge": {
                "comp": "battery",
                "key": "battery__electricity_dc",
            },
            "battery_content": {
                "comp": "battery",
                "key": "battery__None",
            },
            "inverter": {
                "comp": "inverter",
                "key": "inverter__electricity_ac",
            },
            "rectifier": {
                "comp": "rectifier",
                "key": "rectifier__electricity_dc",
            },
            "surplus": {
                "comp": "surplus",
                "key": "electricity_ac__surplus",
            },
            "shortage": {
                "comp": "shortage",
                "key": "shortage__electricity_ac",
            },
            "demand": {
                "comp": "demand",
                "key": "electricity_ac__electricity_demand",
            },
        }

        self.pv = self.energy_system_dict["pv"]
        self.diesel_genset = self.energy_system_dict["diesel_genset"]
        self.battery = self.energy_system_dict["battery"]
        self.inverter = self.energy_system_dict["inverter"]
        self.rectifier = self.energy_system_dict["rectifier"]
        self.shortage = self.energy_system_dict["shortage"]
        self.fuel_density_diesel = 0.846

        for seq, val in self.sequences.items():
            setattr(
                self, f"sequences_{seq}", np.array(results[val["key"]]["sequences"])
            )

        # Fuel consumption conversion
        self.sequences_fuel_consumption_kWh = np.array(
            results["fuel_source__fuel"]["sequences"]
        )

        self.sequences_fuel_consumption = (
            self.sequences_fuel_consumption_kWh
            / self.diesel_genset["parameters"]["fuel_lhv"]
            / self.fuel_density_diesel
        )

        # SCALARS (STATIC)
        def get_capacity(component, result_key):
            if not component["settings"]["is_selected"]:
                return 0
            return (
                json.loads(results[result_key]["scalars"])["invest"]
                if component["settings"].get("design", False)
                else component["parameters"]["nominal_capacity"]
            )

        self.capacity_diesel_genset = get_capacity(
            self.diesel_genset,
            "diesel_genset__electricity_ac",
        )
        self.capacity_pv = get_capacity(self.pv, "pv__electricity_dc")
        self.capacity_inverter = get_capacity(self.inverter, "electricity_dc__inverter")
        self.capacity_rectifier = get_capacity(
            self.rectifier, "electricity_ac__rectifier"
        )
        self.capacity_battery = get_capacity(self.battery, "electricity_dc__battery")

        # Cost and energy calculations
        self.total_renewable = self.annualize(
            sum(
                self.energy_system_dict[comp]["parameters"]["epc"]
                * getattr(self, f"capacity_{comp}")
                for comp in ["pv", "inverter", "battery"]
            )
        )

        self.total_non_renewable = (
            self.annualize(
                sum(
                    self.energy_system_dict[comp]["parameters"]["epc"]
                    * getattr(self, f"capacity_{comp}")
                    for comp in ["diesel_genset", "rectifier"]
                )
            )
            + self.diesel_genset["parameters"]["variable_cost"]
            * self.sequences_genset.sum()
        )

        self.total_component = self.total_renewable + self.total_non_renewable
        self.total_fuel = (
            self.diesel_genset["parameters"]["fuel_cost"]
            * self.sequences_fuel_consumption.sum()
        )
        self.total_revenue = self.total_component + self.total_fuel
        self.total_demand = self.sequences_demand.sum()
        self.lcoe = 100 * self.total_revenue / self.total_demand

        # Key performance indicators
        self.res = (
            100
            * self.sequences_pv.sum()
            / (self.sequences_genset.sum() + self.sequences_pv.sum())
        )
        self.surplus_rate = (
            100
            * self.sequences_surplus.sum()
            / (
                self.sequences_genset.sum()
                - self.sequences_rectifier.sum()
                + self.sequences_inverter.sum()
            )
        )
        self.genset_to_dc = (
            100 * self.sequences_rectifier.sum() / self.sequences_genset.sum()
        )
        self.shortage = (
            100 * self.sequences_shortage.sum() / self.sequences_demand.sum()
        )

        # Output summary
        summary = f"""
        ****************************************
        LCOE:       {self.lcoe:.2f} cent/kWh
        RES:        {self.res:.0f}%
        Surplus:    {self.surplus_rate:.1f}% of the total production
        Shortage:   {self.shortage:.1f}% of the total demand
        AC--DC:     {self.genset_to_dc:.1f}% of the genset production
        ****************************************
        genset:     {self.capacity_diesel_genset:.0f} kW
        pv:         {self.capacity_pv:.0f} kW
        battery:    {self.capacity_battery:.0f} kW
        inverter:   {self.capacity_inverter:.0f} kW
        rectifier:  {self.capacity_rectifier:.0f} kW
        peak:       {self.sequences_demand.max():.0f} kW
        surplus:    {self.sequences_surplus.max():.0f} kW
        ****************************************
        """
        print(summary)

    def supply_results_to_db(self):
        # if len(self.model.solutions) == 0:
        #     if self.infeasible is True:
        #         results = self.results
        #         results.infeasible = self.infeasible
        #         results.save()
        #     return False
        self._process_supply_optimization_results()
        self._emissions_to_db()
        self._results_to_db()
        self._energy_flow_to_db()
        self._demand_curve_to_db()
        self._demand_coverage_to_db()
        self._update_project_status_in_db()

    def _update_project_status_in_db(self):
        # TODO fixup later
        project_setup = self.project
        project_setup.status = "finished"
        # if project_setup.email_notification is True:
        #     user = sync_queries.get_user_by_id(self.user_id)
        #     subject = "PeopleSun: Model Calculation finished"
        #     msg = (
        #         "The calculation of your optimization model is finished. You can view the results at: "
        #         f"\n\n{config.DOMAIN}/simulation_results?project_id={self.project_id}\n"
        #     )
        #     send_mail(user.email, msg, subject=subject)
        project_setup.email_notification = False
        project_setup.save()

    def _demand_coverage_to_db(self):
        df = pd.DataFrame()
        df["demand"] = self.sequences_demand
        df["renewable"] = self.sequences_inverter
        df["non_renewable"] = self.sequences_genset
        df["surplus"] = self.sequences_surplus
        df.index.name = "dt"
        df = df.reset_index()
        df = df.round(3)
        demand_coverage, _ = DemandCoverage.objects.get_or_create(project=self.project)
        json_to_db_model(demand_coverage, df.reset_index(drop=True).to_json())

    def _emissions_to_db(self):
        # TODO check what the source is for these values and link here
        emissions_genset = {
            "small": {"max_capacity": 60, "emission_factor": 1.580},
            "medium": {"max_capacity": 300, "emission_factor": 0.883},
            "large": {"emission_factor": 0.699},
        }
        if self.capacity_diesel_genset < emissions_genset["small"]["max_capacity"]:
            co2_emission_factor = emissions_genset["small"]["emission_factor"]
        elif self.capacity_diesel_genset < emissions_genset["medium"]["max_capacity"]:
            co2_emission_factor = emissions_genset["medium"]["emission_factor"]
        else:
            co2_emission_factor = emissions_genset["large"]["emission_factor"]
        # store fuel co2 emissions (kg_CO2 per L of fuel)
        df = pd.DataFrame()
        df["non_renewable_electricity_production"] = (
            np.cumsum(self.demand) * co2_emission_factor / 1000
        )  # tCO2 per year
        df["hybrid_electricity_production"] = (
            np.cumsum(self.sequences_genset) * co2_emission_factor / 1000
        )  # tCO2 per year
        df.index = pd.date_range("2022-01-01", periods=df.shape[0], freq="h")
        df = df.resample("D").max().reset_index(drop=True)
        emissions, _ = Emissions.objects.get_or_create(project=self.project)
        json_to_db_model(emissions, df.reset_index(drop=True).to_json())

        self.co2_savings = (
            df["non_renewable_electricity_production"]
            - df["hybrid_electricity_production"]
        ).max()
        self.co2_emission_factor = co2_emission_factor

    def _energy_flow_to_db(self):
        energy_flow_df = pd.DataFrame(
            {
                "diesel_genset_production": self.sequences_genset,
                "pv_production": self.sequences_pv,
                "battery_charge": self.sequences_battery_charge,
                "battery_discharge": self.sequences_battery_discharge,
                "battery_content": self.sequences_battery_content,
                "demand": self.sequences_demand,
                "surplus": self.sequences_surplus,
            },
        ).round(3)
        energy_flow, _ = EnergyFlow.objects.get_or_create(project=self.project)
        json_to_db_model(energy_flow, energy_flow_df.reset_index(drop=True).to_json())

    def _demand_curve_to_db(self):
        df = pd.DataFrame()
        df["diesel_genset_duration"] = (
            100 * np.sort(self.sequences_genset)[::-1] / self.sequences_genset.max()
        )
        div = self.sequences_pv.max() if self.sequences_pv.max() > 0 else 1
        df["pv_duration"] = 100 * np.sort(self.sequences_pv)[::-1] / div
        if np.absolute(self.sequences_rectifier).sum() != 0:
            df["rectifier_duration"] = 100 * np.nan_to_num(
                np.sort(self.sequences_rectifier)[::-1]
                / self.sequences_rectifier.max(),
            )
        else:
            df["rectifier_duration"] = 0
        div = self.sequences_inverter.max() if self.sequences_inverter.max() > 0 else 1
        df["inverter_duration"] = 100 * np.sort(self.sequences_inverter)[::-1] / div
        if not self.sequences_battery_charge.max() > 0:
            div = 1
        else:
            div = self.sequences_battery_charge.max()
        df["battery_charge_duration"] = (
            100 * np.sort(self.sequences_battery_charge)[::-1] / div
        )
        if self.sequences_battery_discharge.max() > 0:
            div = self.sequences_battery_discharge.max()
        else:
            div = 1
        df["battery_discharge_duration"] = (
            100 * np.sort(self.sequences_battery_discharge)[::-1] / div
        )
        df = df.copy()
        df.index = pd.date_range("2022-01-01", periods=df.shape[0], freq="h")
        df = df.resample("D").min().reset_index(drop=True)
        df["pv_percentage"] = df.index.copy() / df.shape[0]
        df = df.round(3)
        duration_curve, _ = DurationCurve.objects.get_or_create(project=self.project)
        json_to_db_model(duration_curve, df.reset_index(drop=True).to_json())

    def _results_to_db(self):
        # Annualized cost calculations
        def to_kwh(value):
            """Adapt the order of magnitude (normally from W or Wh oemof results to kWh)"""
            return value / 1000 if value is not None else 0

        results = self.results_obj

        # Handle missing cost_grid case
        if pd.isna(results.cost_grid):
            zero_fields = [
                "n_consumers",
                "n_shs_consumers",
                "n_poles",
                "length_distribution_cable",
                "length_connection_cable",
                "cost_grid",
                "cost_shs",
                "time_grid_design",
                "n_distribution_links",
                "n_connection_links",
                "upfront_invest_grid",
            ]
            for field in zero_fields:
                setattr(results, field, 0)

        results.cost_renewable_assets = self.annualize(self.total_renewable)
        results.cost_non_renewable_assets = self.annualize(self.total_non_renewable)
        results.cost_fuel = self.annualize(self.total_fuel)
        results.cost_grid = self.annualize(results.cost_grid)

        # Financial calculations
        results.epc_total = self.annualize(self.total_revenue + results.cost_grid)
        results.lcoe = (
            100 * (self.total_revenue + results.cost_grid) / self.total_demand
        )

        # System attributes
        results.res = self.res
        results.shortage_total = self.shortage
        results.surplus_rate = self.surplus_rate
        results.peak_demand = self.demand.max()
        results.surplus = self.sequences_surplus.max()
        # TODO no longer needed since sim server should return error
        # results.infeasible = self.infeasible

        # Component capacities
        capacity_fields = {
            "pv_capacity": self.capacity_pv,
            "battery_capacity": self.capacity_battery,
            "inverter_capacity": self.capacity_inverter,
            "rectifier_capacity": self.capacity_rectifier,
            "diesel_genset_capacity": self.capacity_diesel_genset,
        }
        for key, value in capacity_fields.items():
            setattr(results, key, value)

        # Sankey diagram energy flows (all in MWh)
        results.fuel_to_diesel_genset = to_kwh(
            self.sequences_fuel_consumption.sum()
            * 0.846
            * self.diesel_genset["parameters"]["fuel_lhv"]
        )

        results.diesel_genset_to_rectifier = to_kwh(
            self.sequences_rectifier.sum() / self.rectifier["parameters"]["efficiency"]
        )

        results.diesel_genset_to_demand = (
            to_kwh(self.sequences_genset.sum()) - results.diesel_genset_to_rectifier
        )

        results.rectifier_to_dc_bus = to_kwh(self.sequences_rectifier.sum())
        results.pv_to_dc_bus = to_kwh(self.sequences_pv.sum())
        results.battery_to_dc_bus = to_kwh(self.sequences_battery_discharge.sum())
        results.dc_bus_to_battery = to_kwh(self.sequences_battery_charge.sum())

        inverter_efficiency = self.inverter["parameters"].get("efficiency", 1) or 1
        results.dc_bus_to_inverter = to_kwh(
            self.sequences_inverter.sum() / inverter_efficiency
        )

        results.dc_bus_to_surplus = to_kwh(self.sequences_surplus.sum())
        results.inverter_to_demand = to_kwh(self.sequences_inverter.sum())

        # TODO no longer needed
        # results.time_energy_system_design = self.execution_time
        results.co2_savings = self.annualize(self.co2_savings)

        # Demand and shortage statistics
        results.total_annual_consumption = (
            self.demand_full_year.sum() * (100 - self.shortage) / 100
        )
        results.average_annual_demand_per_consumer = (
            self.demand_full_year.mean()
            * (100 - self.shortage)
            / 100
            / self.num_households
            * 1000
        )
        results.base_load = self.demand_full_year.quantile(0.1)
        results.max_shortage = (self.sequences_shortage / self.demand).max() * 100

        # Upfront investment calculations
        investment_fields = {
            "upfront_invest_diesel_gen": "diesel_genset",
            "upfront_invest_pv": "pv",
            "upfront_invest_inverter": "inverter",
            "upfront_invest_rectifier": "rectifier",
            "upfront_invest_battery": "battery",
        }
        for key, component in investment_fields.items():
            setattr(
                results,
                key,
                getattr(results, component + "_capacity")
                * self.energy_system_dict[component]["parameters"]["capex"],
            )

        # Environmental and fuel consumption calculations
        results.co2_emissions = self.annualize(
            self.sequences_genset.sum() * self.co2_emission_factor / 1000
        )
        results.fuel_consumption = self.annualize(self.sequences_fuel_consumption.sum())

        # EPC cost calculations
        epc_fields = {
            "epc_pv": "pv",
            "epc_diesel_genset": "diesel_genset",
            "epc_inverter": "inverter",
            "epc_rectifier": "rectifier",
            "epc_battery": "battery",
        }
        for key, component in epc_fields.items():
            setattr(
                results,
                key,
                self.energy_system_dict[component]["parameters"]["epc"]
                * getattr(self, f"capacity_{component}"),
            )

        results.epc_diesel_genset += self.annualize(
            self.diesel_genset["parameters"]["variable_cost"]
            * self.sequences_genset.sum(axis=0)
        )

        results.save()
