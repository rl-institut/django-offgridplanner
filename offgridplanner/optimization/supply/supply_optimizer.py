"""
The provided module is a comprehensive energy system optimization tool based on the `oemof` framework, a library for
modeling and optimizing energy systems. It's designed to handle various components of an energy system and operates in
two primary modes: dispatch and design.

**Overview of the Module:**

- **Energy System Components Modeled:**
  - **Photovoltaic (PV) Systems:** Models solar power generation.
  - **Diesel Generator Sets (Gensets):** Represents diesel-based power generation.
  - **Batteries:** For energy storage, handling charging and discharging processes.
  - **Inverters and Rectifiers:** Convert electrical energy from DC to AC and vice versa.
  - **Electricity and Fuel Buses:** Act as intermediaries for energy flow within the system.
  - **Shortage and Surplus Handling:** Manages deficits and excesses in energy supply.

- **Operational Modes:**
  - **Dispatch Mode:** In this mode, the capacities of various components (like PV, batteries, and gensets) are
    predetermined. The optimization focuses on the best way to utilize these capacities to meet the demand efficiently.
  - **Design Mode:** Here, the capacities of the components are not fixed and are subject to optimization. The system
    determines the ideal sizes of PV installations, battery storage, and other components to meet energy demands
    cost-effectively.

**Key Functionalities and Processes:**

- **Initialization and Data Handling:**
  - It initializes by fetching project-specific data, including user IDs and project IDs, and retrieves the design
    parameters for the energy system components.
  - Solar potential data is acquired based on location coordinates, and peak demand values are calculated.

- **Optimization Process:**
  - Utilizes `oemof.solph` for optimization, considering various energy flows and storage dynamics.
  - The optimizer sets up energy flows between different components, considering constraints and efficiencies.
  - It calculates costs for different components and handles investments for the design mode.

- **Results Processing and Database Interaction:**
  - After optimization, the results are processed to extract key metrics such as Levelized Cost of Energy (LCOE),
    renewable energy share (RES), surplus electricity, and energy shortfall.
  - The results are then stored in the database, including detailed component capacities, emissions data, and
    financial metrics.

- **Notification and Status Update:**
  - Updates the project status in the database and, if configured, sends email notifications upon completion of the
    optimization process.
"""

import json
import logging
import time

import numpy as np
import pandas as pd
import pyomo.environ as po
from django.http import JsonResponse
from oemof import solph

from config.settings.base import SOLVER_NAME
from offgridplanner.optimization.models import DemandCoverage
from offgridplanner.optimization.models import DurationCurve
from offgridplanner.optimization.models import Emissions
from offgridplanner.optimization.models import EnergyFlow

logger = logging.getLogger(__name__)


def optimize_energy_system(energy_system_json):
    ensys_opt = EnergySystemOptimizer(supply_opt_json=energy_system_json)
    ensys_opt.optimize()
    # ensys_opt.results_to_db()
    # TODO ensys_opt results should be the raw oemof results and the post_processing should be done in projects
    return ensys_opt.results


class EnergySystemOptimizer:
    def __init__(
        self,
        supply_opt_json,
    ):
        print("start es opt")
        supply_opt_dict = json.loads(supply_opt_json)
        energy_system_design = supply_opt_dict["energy_system_design"]
        supply_opt_sequences = supply_opt_dict["sequences"]
        if (
            energy_system_design["pv"]["settings"]["is_selected"] is True
            or energy_system_design["battery"]["settings"]["is_selected"] is True
        ):
            energy_system_design["inverter"]["settings"]["is_selected"] = True
        if energy_system_design["diesel_genset"]["settings"]["is_selected"] is False:
            energy_system_design["inverter"]["settings"]["is_selected"] = True
            energy_system_design["battery"]["settings"]["is_selected"] = True
            energy_system_design["pv"]["settings"]["is_selected"] = True
        solver = SOLVER_NAME
        if solver == "cbc":
            energy_system_design["diesel_genset"]["settings"]["offset"] = False
        self.solver = solver
        self.pv = energy_system_design["pv"]
        self.diesel_genset = energy_system_design["diesel_genset"]
        self.battery = energy_system_design["battery"]
        self.inverter = energy_system_design["inverter"]
        self.rectifier = energy_system_design["rectifier"]
        self.shortage = energy_system_design["shortage"]
        self.fuel_density_diesel = 0.846
        self.dt_index = pd.DatetimeIndex(
            pd.to_datetime(supply_opt_sequences["index"]), freq="h"
        )
        self.demand = pd.Series(supply_opt_sequences["demand"], index=self.dt_index)
        self.solar_potential = pd.Series(
            supply_opt_sequences["solar_potential"], index=self.dt_index
        )
        self.solar_potential_peak = self.solar_potential.max()
        self.demand_peak = self.demand.max()
        self.infeasible = False
        self.energy_system_design = energy_system_design

    def optimize(self):  # noqa: C901,PLR0912,PLR0915 TODO refactor function / build system through tabular instead
        # define an empty dictionary for all epc values
        start_execution_time = time.monotonic()

        energy_system = solph.EnergySystem(
            timeindex=self.dt_index.copy(),
            infer_last_interval=True,
        )
        # TODO this should definitely be simplified with tabular or similar
        # -------------------- BUSES --------------------
        # create electricity and fuel buses
        b_el_ac = solph.Bus(label="electricity_ac")
        b_el_dc = solph.Bus(label="electricity_dc")
        b_fuel = solph.Bus(label="fuel")
        # -------------------- PV --------------------
        # Make decision about different simulation modes of the PV
        if self.pv["settings"]["is_selected"] is False:
            pv = solph.components.Source(
                label="pv",
                outputs={b_el_dc: solph.Flow(nominal_value=0)},
            )
        elif self.pv["settings"]["design"] is True:
            # DESIGN
            pv = solph.components.Source(
                label="pv",
                outputs={
                    b_el_dc: solph.Flow(
                        fix=self.solar_potential / self.solar_potential_peak,
                        nominal_value=None,
                        investment=solph.Investment(
                            ep_costs=self.pv["parameters"]["epc"],
                        ),
                        variable_costs=0,
                    ),
                },
            )
        else:
            # DISPATCH
            pv = solph.components.Source(
                label="pv",
                outputs={
                    b_el_dc: solph.Flow(
                        fix=self.solar_potential / self.solar_potential_peak,
                        nominal_value=self.pv["parameters"]["nominal_capacity"],
                        variable_costs=0,
                    ),
                },
            )

        # -------------------- DIESEL GENSET --------------------
        # fuel density is assumed 0.846 kg/l
        fuel_cost = (
            self.diesel_genset["parameters"]["fuel_cost"]
            / self.fuel_density_diesel
            / self.diesel_genset["parameters"]["fuel_lhv"]
        )
        fuel_source = solph.components.Source(
            label="fuel_source",
            outputs={b_fuel: solph.Flow(variable_costs=fuel_cost)},
        )
        # optimize capacity of the fuel generator
        if self.diesel_genset["settings"]["is_selected"] is False:
            diesel_genset = solph.components.Transformer(
                label="diesel_genset",
                inputs={b_fuel: solph.Flow()},
                outputs={b_el_ac: solph.Flow(nominal_value=0)},
            )
        elif self.diesel_genset["settings"]["design"] is True:
            # DESIGN
            if self.diesel_genset["settings"]["offset"] is True:
                diesel_genset = solph.components.Transformer(
                    label="diesel_genset",
                    inputs={b_fuel: solph.flows.Flow()},
                    outputs={
                        b_el_ac: solph.flows.Flow(
                            nominal_value=None,
                            variable_costs=self.diesel_genset["parameters"][
                                "variable_cost"
                            ],
                            min=self.diesel_genset["parameters"]["min_load"],
                            max=1,
                            nonconvex=solph.NonConvex(),
                            investment=solph.Investment(
                                ep_costs=self.diesel_genset["parameters"]["epc"],
                            ),
                        ),
                    },
                    conversion_factors={
                        b_el_ac: self.diesel_genset["parameters"]["max_efficiency"],
                    },
                )
            else:
                diesel_genset = solph.components.Transformer(
                    label="diesel_genset",
                    inputs={b_fuel: solph.Flow()},
                    outputs={
                        b_el_ac: solph.Flow(
                            nominal_value=None,
                            variable_costs=self.diesel_genset["parameters"][
                                "variable_cost"
                            ],
                            investment=solph.Investment(
                                ep_costs=self.diesel_genset["parameters"]["epc"],
                            ),
                        ),
                    },
                    conversion_factors={
                        b_el_ac: self.diesel_genset["parameters"]["max_efficiency"],
                    },
                )
        else:
            # DISPATCH
            diesel_genset = solph.components.Transformer(
                label="diesel_genset",
                inputs={b_fuel: solph.Flow()},
                outputs={
                    b_el_ac: solph.Flow(
                        nominal_value=self.diesel_genset["parameters"][
                            "nominal_capacity"
                        ],
                        variable_costs=self.diesel_genset["parameters"][
                            "variable_cost"
                        ],
                    ),
                },
                conversion_factors={
                    b_el_ac: self.diesel_genset["parameters"]["max_efficiency"],
                },
            )

        # -------------------- RECTIFIER --------------------

        if self.rectifier["settings"]["is_selected"] is False:
            rectifier = solph.components.Transformer(
                label="rectifier",
                inputs={b_el_ac: solph.Flow(nominal_value=0)},
                outputs={b_el_dc: solph.Flow()},
            )
        elif self.rectifier["settings"]["design"] is True:
            # DESIGN
            rectifier = solph.components.Transformer(
                label="rectifier",
                inputs={
                    b_el_ac: solph.Flow(
                        nominal_value=None,
                        investment=solph.Investment(
                            ep_costs=self.rectifier["parameters"]["epc"],
                        ),
                        variable_costs=0,
                    ),
                },
                outputs={b_el_dc: solph.Flow()},
                conversion_factors={
                    b_el_dc: self.rectifier["parameters"]["efficiency"],
                },
            )
        else:
            # DISPATCH
            rectifier = solph.components.Transformer(
                label="rectifier",
                inputs={
                    b_el_ac: solph.Flow(
                        nominal_value=self.rectifier["parameters"]["nominal_capacity"],
                        variable_costs=0,
                    ),
                },
                outputs={b_el_dc: solph.Flow()},
                conversion_factors={
                    b_el_dc: self.rectifier["parameters"]["efficiency"],
                },
            )

        # -------------------- INVERTER --------------------
        if self.inverter["settings"]["is_selected"] is False:
            inverter = solph.components.Transformer(
                label="inverter",
                inputs={b_el_dc: solph.Flow(nominal_value=0)},
                outputs={b_el_ac: solph.Flow()},
            )
        elif self.inverter["settings"]["design"] is True:
            # DESIGN
            inverter = solph.components.Transformer(
                label="inverter",
                inputs={
                    b_el_dc: solph.Flow(
                        nominal_value=None,
                        investment=solph.Investment(
                            ep_costs=self.inverter["parameters"]["epc"],
                        ),
                        variable_costs=0,
                    ),
                },
                outputs={b_el_ac: solph.Flow()},
                conversion_factors={
                    b_el_ac: self.inverter["parameters"]["efficiency"],
                },
            )
        else:
            # DISPATCH
            inverter = solph.components.Transformer(
                label="inverter",
                inputs={
                    b_el_dc: solph.Flow(
                        nominal_value=self.inverter["parameters"]["nominal_capacity"],
                        variable_costs=0,
                    ),
                },
                outputs={b_el_ac: solph.Flow()},
                conversion_factors={
                    b_el_ac: self.inverter["parameters"]["efficiency"],
                },
            )

        # -------------------- BATTERY --------------------
        if self.battery["settings"]["is_selected"] is False:
            battery = solph.components.GenericStorage(
                label="battery",
                nominal_storage_capacity=0,
                inputs={b_el_dc: solph.Flow()},
                outputs={b_el_dc: solph.Flow()},
            )
        elif self.battery["settings"]["design"] is True:
            # DESIGN
            battery = solph.components.GenericStorage(
                label="battery",
                nominal_storage_capacity=None,
                investment=solph.Investment(
                    ep_costs=self.battery["parameters"]["epc"],
                ),
                inputs={b_el_dc: solph.Flow(variable_costs=0)},
                outputs={b_el_dc: solph.Flow(investment=solph.Investment(ep_costs=0))},
                initial_storage_level=self.battery["parameters"]["soc_max"],
                min_storage_level=self.battery["parameters"]["soc_min"],
                max_storage_level=self.battery["parameters"]["soc_max"],
                balanced=False,
                inflow_conversion_factor=self.battery["parameters"]["efficiency"],
                outflow_conversion_factor=self.battery["parameters"]["efficiency"],
                invest_relation_input_capacity=self.battery["parameters"]["c_rate_in"],
                invest_relation_output_capacity=self.battery["parameters"][
                    "c_rate_out"
                ],
            )
        else:
            # DISPATCH
            battery = solph.components.GenericStorage(
                label="battery",
                nominal_storage_capacity=self.battery["parameters"]["nominal_capacity"],
                inputs={b_el_dc: solph.Flow(variable_costs=0)},
                outputs={b_el_dc: solph.Flow()},
                initial_storage_level=self.battery["parameters"]["soc_max"],
                min_storage_level=self.battery["parameters"]["soc_min"],
                max_storage_level=self.battery["parameters"]["soc_max"],
                balanced=True,
                inflow_conversion_factor=self.battery["parameters"]["efficiency"],
                outflow_conversion_factor=self.battery["parameters"]["efficiency"],
                invest_relation_input_capacity=self.battery["parameters"]["c_rate_in"],
                invest_relation_output_capacity=self.battery["parameters"][
                    "c_rate_out"
                ],
            )

        # -------------------- DEMAND --------------------
        demand_el = solph.components.Sink(
            label="electricity_demand",
            inputs={
                b_el_ac: solph.Flow(
                    # min=1-max_shortage_timestep,
                    fix=self.demand / self.demand_peak,
                    nominal_value=self.demand_peak,
                ),
            },
        )

        # -------------------- SURPLUS --------------------
        surplus = solph.components.Sink(
            label="surplus",
            inputs={b_el_ac: solph.Flow()},
        )

        # -------------------- SHORTAGE --------------------
        # maximal unserved demand and the variable costs of unserved demand.
        if self.shortage["settings"]["is_selected"]:
            shortage = solph.components.Source(
                label="shortage",
                outputs={
                    b_el_ac: solph.Flow(
                        variable_costs=self.shortage["parameters"][
                            "shortage_penalty_cost"
                        ],
                        nominal_value=self.shortage["parameters"]["max_shortage_total"]
                        * sum(self.demand),
                        full_load_time_max=1,
                    ),
                },
            )
        else:
            shortage = solph.components.Source(
                label="shortage",
                outputs={
                    b_el_ac: solph.Flow(
                        nominal_value=0,
                    ),
                },
            )

        # add all objects to the energy system
        energy_system.add(
            pv,
            fuel_source,
            b_el_dc,
            b_el_ac,
            b_fuel,
            inverter,
            rectifier,
            diesel_genset,
            battery,
            demand_el,
            surplus,
            shortage,
        )
        model = solph.Model(energy_system)
        self.execution_time = time.monotonic() - start_execution_time

        def shortage_per_timestep_rule(model, t):
            expr = 0
            ## ------- Get demand at t ------- #
            demand = model.flow[b_el_ac, demand_el, t]
            expr += self.shortage["parameters"]["max_shortage_timestep"] * demand
            ## ------- Get shortage at t------- #
            expr += -model.flow[shortage, b_el_ac, t]

            return expr >= 0

        if self.shortage["settings"]["is_selected"]:
            model.shortage_timestep = po.Constraint(
                model.TIMESTEPS,
                rule=shortage_per_timestep_rule,
            )

        # def max_surplus_electricity_total_rule(model):
        #     max_surplus_electricity = 0.05  # fraction
        #     expr = 0
        #     ## ------- Get generated at t ------- #
        #     generated_diesel_genset = sum(model.flow[diesel_genset, b_el_ac, :])
        #     generated_pv = sum(model.flow[inverter, b_el_ac, :])
        #     ac_to_dc = sum(model.flow[b_el_ac, rectifier, :])
        #     generated = generated_diesel_genset + generated_pv - ac_to_dc
        #     expr += (generated * max_surplus_electricity)
        #     ## ------- Get surplus at t------- #
        #     surplus_total = sum(model.flow[b_el_ac, surplus, :])
        #     expr += -surplus_total

        #     return expr >= 0

        # model.max_surplus_electricity_total = po.Constraint(
        #     rule=max_surplus_electricity_total_rule
        # )

        # optimize the energy system
        # gurobi --> 'MipGap': '0.01'
        # cbc --> 'ratioGap': '0.01'
        solver_option = {"gurobi": {"MipGap": "0.03"}, "cbc": {"ratioGap": "0.03"}}

        res = model.solve(
            solver=self.solver,
            solve_kwargs={"tee": True},
            cmdline_options=solver_option[self.solver],
        )
        # self.model = model
        if len(model.solutions) > 0:
            energy_system.results["meta"] = solph.processing.meta_results(model)
            results = solph.processing.results(model)
            return results
        else:
            print("No solution found")
            if next(iter(res["Solver"]))["Termination condition"] == "infeasible":
                self.infeasible = True
                return JsonResponse(
                    {"message": "The performed optimization is infeasible"}
                )
            return JsonResponse({"message": "An error ocurred during the optimization"})

    def _process_results(self):
        nodes = [
            "pv",
            "fuel_source",
            "diesel_genset",
            "inverter",
            "rectifier",
            "battery",
            "electricity_demand",
            "surplus",
            "shortage",
        ]
        results = {
            node: solph.views.node(self.results_main, node=node) for node in nodes
        }

        #  SEQUENCES (DYNAMIC)
        self.sequences_demand = results["electricity_demand"]["sequences"][
            (("electricity_ac", "electricity_demand"), "flow")
        ]

        self.sequences = {
            "pv": {"comp": "pv", "key": (("pv", "electricity_dc"), "flow")},
            "genset": {
                "comp": "diesel_genset",
                "key": (("diesel_genset", "electricity_ac"), "flow"),
            },
            "battery_charge": {
                "comp": "battery",
                "key": (("electricity_dc", "battery"), "flow"),
            },
            "battery_discharge": {
                "comp": "battery",
                "key": (("battery", "electricity_dc"), "flow"),
            },
            "battery_content": {
                "comp": "battery",
                "key": (("battery", "None"), "storage_content"),
            },
            "inverter": {
                "comp": "inverter",
                "key": (("inverter", "electricity_ac"), "flow"),
            },
            "rectifier": {
                "comp": "rectifier",
                "key": (("rectifier", "electricity_dc"), "flow"),
            },
            "surplus": {
                "comp": "surplus",
                "key": (("electricity_ac", "surplus"), "flow"),
            },
            "shortage": {
                "comp": "shortage",
                "key": (("shortage", "electricity_ac"), "flow"),
            },
        }

        for seq, val in self.sequences.items():
            setattr(
                self, f"sequences_{seq}", results[val["comp"]]["sequences"][val["key"]]
            )

        # Fuel consumption conversion
        self.sequences_fuel_consumption = (
            results["fuel_source"]["sequences"][("fuel_source", "fuel"), "flow"]
            / self.diesel_genset["parameters"]["fuel_lhv"]
            / self.fuel_density_diesel
        )
        self.sequences_fuel_consumption_kWh = results["fuel_source"]["sequences"][
            ("fuel_source", "fuel"), "flow"
        ]

        # SCALARS (STATIC)
        def get_capacity(component, result_key, invest_key):
            if not component["settings"]["is_selected"]:
                return 0
            return (
                results[result_key]["scalars"][invest_key]
                if component["settings"].get("design", False)
                else component["parameters"]["nominal_capacity"]
            )

        self.capacity_diesel_genset = get_capacity(
            self.diesel_genset,
            "diesel_genset",
            (("diesel_genset", "electricity_ac"), "invest"),
        )
        self.capacity_pv = get_capacity(
            self.pv, "pv", (("pv", "electricity_dc"), "invest")
        )
        self.capacity_inverter = get_capacity(
            self.inverter, "inverter", (("electricity_dc", "inverter"), "invest")
        )
        self.capacity_rectifier = get_capacity(
            self.rectifier, "rectifier", (("electricity_ac", "rectifier"), "invest")
        )
        self.capacity_battery = get_capacity(
            self.battery, "battery", (("electricity_dc", "battery"), "invest")
        )

        # Cost and energy calculations
        self.total_renewable = (
            sum(
                self.epc[comp] * getattr(self, f"capacity_{comp}")
                for comp in ["pv", "inverter", "battery"]
            )
            * self.n_days
            / 365
        )

        self.total_non_renewable = (
            sum(
                self.epc[comp] * getattr(self, f"capacity_{comp}")
                for comp in ["diesel_genset", "rectifier"]
            )
            * self.n_days
            / 365
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

    def results_to_db(self):
        if len(self.model.solutions) == 0:
            if self.infeasible is True:
                results = self.results
                results.infeasible = self.infeasible
                results.save()
            return False
        self._emissions_to_db()
        self._results_to_db()
        self._energy_flow_to_db()
        self._demand_curve_to_db()
        self._demand_coverage_to_db()
        self._update_project_status_in_db()
        return True

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
        demand_coverage.data = df.reset_index(drop=True).to_json()
        demand_coverage.save()

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
        emissions.data = df.reset_index(drop=True).to_json()
        emissions.save()
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
        energy_flow.data = energy_flow_df.reset_index(drop=True).to_json()
        energy_flow.save()

    def _demand_curve_to_db(self):
        df = pd.DataFrame()
        df["diesel_genset_duration"] = (
            100 * np.sort(self.sequences_genset)[::-1] / self.sequences_genset.max()
        )
        div = self.sequences_pv.max() if self.sequences_pv.max() > 0 else 1
        df["pv_duration"] = 100 * np.sort(self.sequences_pv)[::-1] / div
        if self.sequences_rectifier.abs().sum() != 0:
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
        duration_curve.data = df.reset_index(drop=True).to_json()
        duration_curve.save()

    def _results_to_db(self):
        # Annualized cost calculations
        def annualize(value):
            return value / self.n_days * 365 if value is not None else 0

        def to_kwh(value):
            """Adapt the order of magnitude (normally from W or Wh oemof results to kWh)"""
            return value / 1000 if value is not None else 0

        results = self.results

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

        results.cost_renewable_assets = annualize(self.total_renewable)
        results.cost_non_renewable_assets = annualize(self.total_non_renewable)
        results.cost_fuel = annualize(self.total_fuel)
        results.cost_grid = annualize(results.cost_grid)

        # Financial calculations
        results.epc_total = annualize(self.total_revenue + results.cost_grid)
        results.lcoe = (
            100 * (self.total_revenue + results.cost_grid) / self.total_demand
        )

        # System attributes
        results.res = self.res
        results.shortage_total = self.shortage
        results.surplus_rate = self.surplus_rate
        results.peak_demand = self.demand.max()
        results.surplus = self.sequences_surplus.max()
        results.infeasible = self.infeasible

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

        results.time_energy_system_design = self.execution_time
        results.co2_savings = annualize(self.co2_savings)

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
                * self.energy_system_design[component]["parameters"]["capex"],
            )

        # Environmental and fuel consumption calculations
        results.co2_emissions = annualize(
            self.sequences_genset.sum() * self.co2_emission_factor / 1000
        )
        results.fuel_consumption = annualize(self.sequences_fuel_consumption.sum())

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
                self.epc[component] * getattr(self, f"capacity_{component}"),
            )

        results.epc_diesel_genset += annualize(
            self.diesel_genset["parameters"]["variable_cost"]
            * self.sequences_genset.sum(axis=0)
        )

        results.save()
