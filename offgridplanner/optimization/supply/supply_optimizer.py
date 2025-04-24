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

import pandas as pd
import pyomo.environ as po
from django.http import JsonResponse
from oemof import solph

from config.settings.base import SOLVER_NAME

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
