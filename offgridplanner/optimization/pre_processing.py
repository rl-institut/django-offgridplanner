# Pre- and post-processing for the grid and supply optimization
import json
from io import StringIO

import pandas as pd
from django.shortcuts import get_object_or_404

from offgridplanner.optimization.models import Nodes
from offgridplanner.optimization.supply.demand_estimation import get_demand_timeseries
from offgridplanner.optimization.supply.solar_potential import (
    get_dc_feed_in_sync_db_query,
)
from offgridplanner.projects.models import Project


class PreProcessor:
    """
    Replaces the previous class BaseOptimizer by calculating values needed for the optimization. Used to create
    jsons sent to the actual optimizer / simulation server
    """

    def __init__(self, proj_id):
        self.project = get_object_or_404(Project, id=proj_id)
        self.options = self.project.options
        self.tax = 0
        self.wacc = self.project.interest_rate / 100
        self.project_lifetime = self.project.lifetime
        self.crf = (self.wacc * (1 + self.wacc) ** self.project_lifetime) / (
            (1 + self.wacc) ** self.project_lifetime - 1
        )
        self.energy_system_dict = self.project.energysystemdesign.to_nested_dict()

    @staticmethod
    def annualize(n_days, value):
        return value / n_days * 365 if value is not None else 0

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

    def epc(self, component):
        component_dict = self.energy_system_dict[component]
        epc = (
            self.crf
            * self.capex_multi_investment(
                capex_0=component_dict["parameters"]["capex"],
                component_lifetime=component_dict["parameters"]["lifetime"],
            )
            + component_dict["parameters"]["opex"]
        )
        epc = self.annualize(self.project.n_days, epc)

        return epc

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
        :param proj_id:
        :return: json
        """

        demand = self.collect_project_demand()
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

        # TODO why does this need .loc[dt_index], it should directly be fetching only the necessary timesteps
        solar_potential = get_dc_feed_in_sync_db_query(
            lat,
            lon,
            dt_index,
        )
        sequences = {
            "index": demand.index.strftime("%Y-%m-%dT%H:%M:%S").tolist(),
            "demand": demand.to_numpy().tolist(),
            "solar_potential": solar_potential.to_numpy().tolist(),
        }
        energy_system_design = self.energy_system_dict
        for component in energy_system_design.keys():  # noqa:SIM118 (avoid changing dictionary in loop, using keys copy instead)
            if component != "shortage":
                energy_system_design[component]["parameters"]["epc"] = self.epc(
                    component
                )
                # delete parameters that are no longer needed for the optimization (reduce size of the json)
                del energy_system_design[component]["parameters"]["capex"]
                del energy_system_design[component]["parameters"]["opex"]
                del energy_system_design[component]["parameters"]["lifetime"]

        supply_opt_json = json.dumps(
            {"sequences": sequences, "energy_system_design": energy_system_design}
        )

        return supply_opt_json
