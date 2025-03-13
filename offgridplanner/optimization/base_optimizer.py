"""
The `BaseOptimizer` class in this module serves as the parent class for both grid and energy system optimizers in the
FastAPI application. It provides core functionalities and attributes common to both optimizer types. Key features
include:

Initialization: It initializes attributes based on user and project identifiers, retrieving project setup
details from the database.

Time Frame Handling: The class sets up the operational time frame for optimization, including start dates and
hourly datetime indices.

Financial Parameters: It calculates financial parameters like weighted average cost of capital (`wacc`) and
capital recovery factor (`crf`), crucial for investment analysis.

Demand Calculation: The class computes the electricity demand profile, a key input for grid and energy system
capacity planning.

CAPEX Calculation: A method to calculate equivalent capital expenditure for components with lifetimes shorter
than the project duration, factoring in replacements and financial aspects.

This class forms the foundation for the more specialized `GridOptimizer` and `EnergySystemOptimizer` classes, ensuring
code reusability and a structured approach to optimization within the application.
"""

import os
from io import StringIO

import pandas as pd

from offgridplanner.optimization.models import Results
from offgridplanner.optimization.supply.demand_estimation import get_demand_timeseries
from offgridplanner.projects.models import *


class BaseOptimizer:
    """
    This is a general parent class for both grid and energy system optimizers
    """

    def __init__(self, proj_id):
        print("Initiating base optimizer...")
        self.project = Project.objects.get(id=proj_id)
        self.project_dict = model_to_dict(self.project)
        self.simulation = self.project.simulation
        self.results, _ = Results.objects.get_or_create(simulation=self.simulation)
        self.opts_dict = model_to_dict(self.project.options)
        self.grid_design_dict = model_to_dict(self.project.griddesign)
        self.custom_demand_dict = model_to_dict(self.project.customdemand)

        # self.user_id = user_id
        # self.project_id = project_id
        self.n_days = min(
            self.project_dict["n_days"], int(os.environ.get("MAX_DAYS", 365))
        )
        # TODO fix date to actual start_date
        # self.start_datetime = pd.to_datetime(self.project_dict["start_date"]).to_pydatetime()
        # start_datetime hardcoded as only 2022 pv and demand data is available
        self.start_datetime = pd.to_datetime("2022").to_pydatetime()
        self.dt_index = pd.date_range(
            self.start_datetime,
            self.start_datetime + pd.to_timedelta(self.n_days, unit="D"),
            freq="h",
            inclusive="left",
        )
        self.project_lifetime = self.project_dict["lifetime"]
        self.wacc = self.project_dict["interest_rate"] / 100
        self.tax = 0
        self.crf = (self.wacc * (1 + self.wacc) ** self.project_lifetime) / (
            (1 + self.wacc) ** self.project_lifetime - 1
        )
        if (
            self.opts_dict["do_demand_estimation"]
            or self.opts_dict["do_grid_optimization"]
        ):
            self.nodes = self.project.nodes.df
        else:
            self.nodes = pd.DataFrame()
        if self.opts_dict["do_demand_estimation"]:
            self.demand_full_year = get_demand_timeseries(
                self.project.nodes, self.project.customdemand
            ).sum(axis=1)

            self.demand = self.demand_full_year.iloc[: (self.n_days * 24)]
        else:
            uploaded_data = self.project.customdemand.uploaded_data
            self.demand = pd.read_json(StringIO(uploaded_data))["demand"]
            # TODO error is thrown for annual total consumption if full year demand is not defined - tbd fix
            if self.n_days == 365:
                self.demand_full_year = self.demand

    def capex_multi_investment(self, capex_0, component_lifetime):
        """
        Calculates the equivalent CAPEX for components with lifetime less than the project lifetime.

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
