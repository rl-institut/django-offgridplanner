# Pre- and post-processing for the grid and supply optimization
import json
from io import StringIO

import numpy as np
import pandas as pd
import requests
from django.shortcuts import get_object_or_404
from jsonschema import validate

from config.settings.base import SIM_API_HOST
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

    @staticmethod
    def validate_json_with_server_schema(json_obj, model, direction):
        """Request the corresponding schema from the optimization server and validate against json
        Parameters:
            json_obj (dict): JSON object to be validated
            model (str): Either "grid" or "supply"
            direction (str): Either "input" or "output"
        """
        response = requests.get(
            f"{SIM_API_HOST}/schema/{model}/{direction}", timeout=10
        )
        schema = response.json()

        validate(instance=json_obj, schema=schema)

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

        start_datetime = pd.to_datetime("2022")
        dt_index = pd.date_range(
            start_datetime,
            start_datetime + pd.to_timedelta(self.project.n_days, unit="D"),
            freq="h",
            inclusive="left",
        )

        start_date_for_json = start_datetime.isoformat()

        solar_potential = get_dc_feed_in_sync_db_query(
            lat,
            lon,
            dt_index,
        )

        sequences = {
            "index": {
                "start_date": start_date_for_json,
                "n_days": self.project.n_days,
                "freq": "h",
            },
            "demand": self.demand.to_numpy().tolist(),
            "solar_potential": solar_potential.to_numpy().tolist(),
        }
        energy_system_design = self.energy_system_dict

        # calculate periodical costs of components out of input capex, opex and lifetime

        supply_opt_json = {
            "sequences": sequences,
            "energy_system_design": energy_system_design,
        }

        self.validate_json_with_server_schema(supply_opt_json, "supply", "input")
        return supply_opt_json

    def collect_grid_opt_json_data(self):
        nodes_df = self.project.nodes.df.copy()
        nodes_df = nodes_df.reset_index(drop=False)
        nodes_df = nodes_df.rename(columns={"index": "id"})
        nodes_records = nodes_df.to_dict(orient="records")

        node_fields = [
            "id",
            "how_added",
            "node_type",
            "consumer_type",
            "custom_specification",
            "shs_options",
            "consumer_detail",
            "is_connected",
            "coordinates",
        ]

        for node in nodes_records:
            if "latitude" in node and "longitude" in node:
                node["coordinates"] = [node.pop("latitude"), node.pop("longitude")]
            else:
                node["coordinates"] = None

        nodes_values = [
            [node.get(field, None) for field in node_fields] for node in nodes_records
        ]

        grid_opt_json = {
            "nodes": self.project.nodes.df.to_dict(orient="list"),
            "grid_design": self.grid_design_dict,
            "yearly_demand": self.demand.sum(),
        }

        # validate the JSON with the schema from the simulation server
        self.validate_json_with_server_schema(grid_opt_json, "grid", "input")
        return grid_opt_json


class GridProcessor(OptimizationDataHandler):
    def __init__(self, results_json, proj_id):
        super().__init__(proj_id)
        self.validate_json_with_server_schema(results_json, "grid", "output")
        self.results_obj, _ = Results.objects.get_or_create(
            simulation=self.project.simulation
        )
        self.nodes_obj, _ = Nodes.objects.get_or_create(project=self.project)
        self.links_obj, _ = Links.objects.get_or_create(project=self.project)
        self.grid_results = results_json
        self.nodes_df = pd.DataFrame(self.grid_results["nodes"])
        self.links_df = pd.DataFrame(self.grid_results["links"])

    def grid_results_to_db(self):
        # read the nodes and links data and save to the database
        self.nodes_obj.data = self.nodes_df.to_json()
        self.links_obj.data = self.links_df.to_json()
        self.nodes_obj.save()
        self.links_obj.save()
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
        self.validate_json_with_server_schema(results_json, "supply", "output")
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

    def process_supply_optimization_results(self):
        """Extract and compute everything needed from the supply optimization result."""
        self._extract_sequences()
        self._calculate_capacities()
        self._calculate_costs()
        self._calculate_kpis()
        self._calculate_emissions()

    def _extract_sequences(self):
        results = self.supply_results
        self.sequences = {
            "pv": np.array(results["pv__electricity_dc"]["sequences"]),
            "genset": np.array(results["diesel_genset__electricity_ac"]["sequences"]),
            "battery_charge": np.array(results["electricity_dc__battery"]["sequences"]),
            "battery_discharge": np.array(
                results["battery__electricity_dc"]["sequences"]
            ),
            "battery_content": np.array(results["battery__None"]["sequences"]),
            "inverter": np.array(results["inverter__electricity_ac"]["sequences"]),
            "rectifier": np.array(results["rectifier__electricity_dc"]["sequences"]),
            "surplus": np.array(results["electricity_ac__surplus"]["sequences"]),
            "shortage": np.array(results["shortage__electricity_ac"]["sequences"]),
            "demand": np.array(
                results["electricity_ac__electricity_demand"]["sequences"]
            ),
            "fuel_consumption_kwh": np.array(results["fuel_source__fuel"]["sequences"]),
        }

        diesel = self.energy_system_dict["diesel_genset"]["parameters"]
        fuel_density_diesel = 0.846
        self.sequences["fuel_consumption_l"] = (
            self.sequences["fuel_consumption_kwh"]
            / diesel["fuel_lhv"]
            / fuel_density_diesel
        )

        # Generate energy flow df from extracted sequences
        self.energy_flow_df = pd.DataFrame(
            {
                "diesel_genset_production": self.sequences["genset"],
                "pv_production": self.sequences["pv"],
                "battery_charge": self.sequences["battery_charge"],
                "battery_discharge": self.sequences["battery_discharge"],
                "battery_content": self.sequences["battery_content"],
                "demand": self.sequences["demand"],
                "surplus": self.sequences["surplus"],
            },
        ).round(3)

        # Generate demand coverage df from extracted sequences
        self.demand_coverage_df = (
            pd.DataFrame(
                {
                    "demand": self.sequences["demand"],
                    "renewable": self.sequences["inverter"],
                    "non_renewable": self.sequences["genset"],
                    "surplus": self.sequences["surplus"],
                }
            )
            .reset_index()
            .round(3)
        )

        # Generate duration curve df from extracted sequences
        def duration_sequence(comp):
            flow = self.sequences[comp]
            duration = 100 * np.nan_to_num(np.sort(flow)[::-1])
            div = self.sequences[comp].max() if flow.max() != 0 else 1

            norm_duration = duration / div
            return norm_duration

        self.duration_curve_df = pd.DataFrame(
            {
                "diesel_genset_duration": duration_sequence("genset"),
                "pv_duration": duration_sequence("pv"),
                "rectifier_duration": duration_sequence("rectifier"),
                "inverter_duration": duration_sequence("inverter"),
                "battery_charge_duration": duration_sequence("battery_charge"),
                "battery_discharge_duration": duration_sequence("battery_discharge"),
            }
        ).round(3)

        self.duration_curve_df.index = pd.date_range(
            "2022-01-01", periods=self.duration_curve_df.shape[0], freq="h"
        )
        self.duration_curve_df = (
            self.duration_curve_df.resample("D").min().reset_index(drop=True)
        )
        self.duration_curve_df["pv_percentage"] = (
            self.duration_curve_df.index.copy() / self.duration_curve_df.shape[0]
        )

    def _calculate_capacities(self):
        def get_capacity(comp_name, result_key):
            comp = self.energy_system_dict[comp_name]
            if not comp["settings"]["is_selected"]:
                return 0
            return (
                json.loads(self.supply_results[result_key]["scalars"])["invest"]
                if comp["settings"].get("design", False)
                else comp["parameters"]["nominal_capacity"]
            )

        self.capacities = {
            "pv": get_capacity("pv", "pv__electricity_dc"),
            "diesel_genset": get_capacity(
                "diesel_genset", "diesel_genset__electricity_ac"
            ),
            "inverter": get_capacity("inverter", "electricity_dc__inverter"),
            "rectifier": get_capacity("rectifier", "electricity_ac__rectifier"),
            "battery": get_capacity("battery", "electricity_dc__battery"),
        }

    def _calculate_costs(self):
        def epc_cost(comp):
            return (
                self.energy_system_dict[comp]["parameters"]["epc"]
                * self.capacities[comp]
            )

        self.total_renewable = self.annualize(
            sum(epc_cost(comp) for comp in ["pv", "inverter", "battery"])
        )
        self.total_non_renewable = (
            self.annualize(
                sum(epc_cost(comp) for comp in ["diesel_genset", "rectifier"])
            )
            + self.energy_system_dict["diesel_genset"]["parameters"]["variable_cost"]
            * self.sequences["genset"].sum()
        )

        self.total_component = self.total_renewable + self.total_non_renewable
        self.total_fuel = self.annualize(
            self.energy_system_dict["diesel_genset"]["parameters"]["fuel_cost"]
            * self.sequences["fuel_consumption_l"].sum()
        )
        self.total_revenue = self.total_component + self.total_fuel
        self.total_demand = self.sequences["demand"].sum()

    def _calculate_kpis(self):
        self.lcoe = 100 * self.total_revenue / self.total_demand
        self.res = (
            100
            * (self.total_demand - self.sequences["genset"].sum())
            / self.total_demand
        )
        self.surplus_rate = (
            100
            * self.sequences["surplus"].sum()
            / (
                self.sequences["genset"].sum()
                - self.sequences["rectifier"].sum()
                + self.sequences["inverter"].sum()
            )
        )
        self.genset_to_dc = (
            100 * self.sequences["rectifier"].sum() / self.sequences["genset"].sum()
        )
        self.shortage = (
            100 * self.sequences["shortage"].sum() / self.sequences["demand"].sum()
        )

    def _calculate_emissions(self):
        #  Emissions calculations
        # TODO check the source for these
        emissions_factors = {
            "small": {"max_capacity": 60, "factor": 1.580},
            "medium": {"max_capacity": 300, "factor": 0.883},
            "large": {"factor": 0.699},
        }

        genset_capacity = self.capacities["diesel_genset"]
        if genset_capacity < emissions_factors["small"]["max_capacity"]:
            self.co2_emission_factor = emissions_factors["small"]["factor"]
        elif genset_capacity < emissions_factors["medium"]["max_capacity"]:
            self.co2_emission_factor = emissions_factors["medium"]["factor"]
        else:
            self.co2_emission_factor = emissions_factors["large"]["factor"]

        # Store emissions time series
        self.emissions_df = pd.DataFrame()
        self.emissions_df["non_renewable_electricity_production"] = (
            np.cumsum(self.demand) * self.co2_emission_factor / 1000
        )
        self.emissions_df["hybrid_electricity_production"] = (
            np.cumsum(self.sequences["genset"]) * self.co2_emission_factor / 1000
        )

        self.co2_emissions = self.annualize(
            self.sequences["genset"].sum() * self.co2_emission_factor / 1000
        )
        self.co2_savings = (
            self.emissions_df["non_renewable_electricity_production"]
            - self.emissions_df["hybrid_electricity_production"]
        ).max()
        self.annual_co2_savings = self.annualize(self.co2_savings)

        self.emissions_df.index = pd.date_range(
            "2022-01-01", periods=self.emissions_df.shape[0], freq="h"
        )
        self.emissions_df = self.emissions_df.resample("D").max().reset_index(drop=True)

    def _parsed_dataframes_to_db(self):
        mapping = {
            EnergyFlow: self.energy_flow_df,
            DurationCurve: self.duration_curve_df,
            DemandCoverage: self.demand_coverage_df,
            Emissions: self.emissions_df,
        }
        for model_cls, df in mapping.items():
            obj, _ = model_cls.objects.get_or_create(project=self.project)
            obj.data = df.to_json()
            obj.save()

    def supply_results_to_db(self):
        self._parsed_dataframes_to_db()
        self._scalar_results_to_db()
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

    def _scalar_results_to_db(self):
        # Annualized cost calculations
        results = self.results_obj

        # --- Financial costs ---
        results.cost_renewable_assets = self.total_renewable
        results.cost_non_renewable_assets = self.total_non_renewable
        results.cost_fuel = self.total_fuel
        results.epc_total = self.total_revenue + (results.cost_grid or 0)
        results.lcoe = 100 * results.epc_total / self.total_demand

        # --- Key performance indicators ---
        results.res = self.res
        results.shortage_total = self.shortage
        results.surplus_rate = self.surplus_rate
        results.peak_demand = self.demand.max()
        results.surplus = self.sequences["surplus"].max()

        # --- Component capacities ---
        results.pv_capacity = self.capacities["pv"]
        results.battery_capacity = self.capacities["battery"]
        results.inverter_capacity = self.capacities["inverter"]
        results.rectifier_capacity = self.capacities["rectifier"]
        results.diesel_genset_capacity = self.capacities["diesel_genset"]

        # --- Sankey energy flows ---
        results.fuel_to_diesel_genset = self.sequences["fuel_consumption_kwh"].sum()
        results.diesel_genset_to_rectifier = (
            self.sequences["rectifier"].sum()
            / self.energy_system_dict["rectifier"]["parameters"]["efficiency"]
        )
        results.diesel_genset_to_demand = (
            self.sequences["genset"].sum() - results.diesel_genset_to_rectifier
        )
        results.rectifier_to_dc_bus = self.sequences["rectifier"].sum()
        results.pv_to_dc_bus = self.sequences["pv"].sum()
        results.battery_to_dc_bus = self.sequences["battery_discharge"].sum()
        results.dc_bus_to_battery = self.sequences["battery_charge"].sum()
        results.dc_bus_to_inverter = (
            self.sequences["inverter"].sum()
            / self.energy_system_dict["inverter"]["parameters"]["efficiency"]
        )
        results.dc_bus_to_surplus = self.sequences["surplus"].sum()
        results.inverter_to_demand = self.sequences["inverter"].sum()

        # --- Demand and shortage statistics ---
        results.total_annual_consumption = (
            self.demand_full_year.sum() * (100 - self.shortage) / 100
        )
        results.average_annual_demand_per_consumer = (
            self.demand_full_year.mean()
            * (100 - self.shortage)
            / 100
            / self.num_households
        )
        results.base_load = self.demand_full_year.quantile(0.1)
        results.max_shortage = (self.sequences["shortage"] / self.demand).max() * 100

        # --- Upfront investment ---
        for key in ["pv", "diesel_genset", "inverter", "rectifier", "battery"]:
            capex = self.energy_system_dict[key]["parameters"]["capex"]
            capacity = self.capacities[key]
            setattr(results, f"upfront_invest_{key}", capex * capacity)

        # --- EPC (annualized) ---
        for key in ["pv", "diesel_genset", "inverter", "rectifier", "battery"]:
            epc = self.energy_system_dict[key]["parameters"]["epc"]
            value = epc * self.capacities[key]

            if key == "diesel_genset":
                value += self.annualize(
                    self.energy_system_dict[key]["parameters"]["variable_cost"]
                    * self.sequences["genset"].sum()
                )

            setattr(results, f"epc_{key}", value)

        # --- Emissions ---
        results.co2_emissions = self.co2_emissions
        results.co2_savings = self.annual_co2_savings

        results.save()
