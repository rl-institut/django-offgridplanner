from collections import defaultdict
from django.db import models
from offgridplanner.projects.models import Project


class CustomDemand(models.Model):
    # Corresponds to class Demand in tier_spatial planning, removed fields id (obsolete), use_custom_demand and use_custom_shares
    # (one or both of them should just be None in database if not used), and household_option (not sure what it is used for)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, null=True)
    very_low = models.FloatField(default=0.663)
    low = models.FloatField(default=0.215)
    middle = models.FloatField(default=0.076)
    high = models.FloatField(default=0.031)
    very_high = models.FloatField(default=0.015)
    annual_total_consumption = models.FloatField(blank=True, null=True)
    annual_peak_consumption = models.FloatField(blank=True, null=True)
    uploaded_data = models.JSONField(null=True)

    @property
    def calibration_option(self):
        if (
            self.annual_total_consumption is None
            and self.annual_peak_consumption is None
        ):
            return None

        calibration_option = (
            "annual_total_consumption"
            if self.annual_total_consumption is not None
            else "annual_peak_consumption"
        )
        return calibration_option


class GridDesign(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, null=True)
    distribution_cable_lifetime = models.PositiveSmallIntegerField(
        default=25, db_column="distribution_cable__lifetime"
    )
    distribution_cable_capex = models.FloatField(
        default=10, db_column="distribution_cable__capex"
    )
    distribution_cable_max_length = models.FloatField(
        default=50, db_column="distribution_cable__max_length"
    )
    connection_cable_lifetime = models.PositiveSmallIntegerField(
        default=25, db_column="connection_cable__lifetime"
    )
    connection_cable_capex = models.FloatField(
        default=4, db_column="connection_cable__capex"
    )
    connection_cable_max_length = models.FloatField(
        default=20, db_column="connection_cable__max_length"
    )
    pole_lifetime = models.PositiveSmallIntegerField(
        default=25, db_column="pole__lifetime"
    )
    pole_capex = models.FloatField(default=800, db_column="pole__capex")
    pole_max_n_connections = models.PositiveSmallIntegerField(
        default=5, db_column="pole__max_n_connections"
    )
    mg_connection_cost = models.FloatField(default=140, db_column="mg__connection_cost")
    include_shs = models.BooleanField(default=True, db_column="shs__include")
    shs_max_grid_cost = models.FloatField(
        default=0.6, blank=True, null=True, db_column="shs__max_grid_cost"
    )


class EnergySystemDesign(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, null=True)
    battery_settings_is_selected = models.BooleanField(
        db_column="battery__settings__is_selected",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_settings_design = models.BooleanField(
        db_column="battery__settings__design",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_nominal_capacity = models.FloatField(
        db_column="battery__parameters__nominal_capacity",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_lifetime = models.PositiveIntegerField(
        db_column="battery__parameters__lifetime",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_capex = models.FloatField(
        db_column="battery__parameters__capex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_opex = models.FloatField(
        db_column="battery__parameters__opex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_soc_min = models.FloatField(
        db_column="battery__parameters__soc_min",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_soc_max = models.FloatField(
        db_column="battery__parameters__soc_max",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_c_rate_in = models.FloatField(
        db_column="battery__parameters__c_rate_in",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_c_rate_out = models.FloatField(
        db_column="battery__parameters__c_rate_out",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    battery_parameters_efficiency = models.FloatField(
        db_column="battery__parameters__efficiency",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_settings_is_selected = models.BooleanField(
        db_column="diesel_genset__settings__is_selected",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_settings_design = models.BooleanField(
        db_column="diesel_genset__settings__design",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_nominal_capacity = models.FloatField(
        db_column="diesel_genset__parameters__nominal_capacity",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_lifetime = models.PositiveIntegerField(
        db_column="diesel_genset__parameters__lifetime",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_capex = models.FloatField(
        db_column="diesel_genset__parameters__capex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_opex = models.FloatField(
        db_column="diesel_genset__parameters__opex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_variable_cost = models.FloatField(
        db_column="diesel_genset__parameters__variable_cost",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_fuel_cost = models.FloatField(
        db_column="diesel_genset__parameters__fuel_cost",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_fuel_lhv = models.FloatField(
        db_column="diesel_genset__parameters__fuel_lhv",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_min_load = models.FloatField(
        db_column="diesel_genset__parameters__min_load",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_max_load = models.FloatField(
        db_column="diesel_genset__parameters__max_load",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_min_efficiency = models.FloatField(
        db_column="diesel_genset__parameters__min_efficiency",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    diesel_genset_parameters_max_efficiency = models.FloatField(
        db_column="diesel_genset__parameters__max_efficiency",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    inverter_settings_is_selected = models.BooleanField(
        db_column="inverter__settings__is_selected",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    inverter_settings_design = models.BooleanField(
        db_column="inverter__settings__design",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    inverter_parameters_nominal_capacity = models.FloatField(
        db_column="inverter__parameters__nominal_capacity",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    inverter_parameters_lifetime = models.PositiveIntegerField(
        db_column="inverter__parameters__lifetime",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    inverter_parameters_capex = models.FloatField(
        db_column="inverter__parameters__capex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    inverter_parameters_opex = models.FloatField(
        db_column="inverter__parameters__opex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    inverter_parameters_efficiency = models.FloatField(
        db_column="inverter__parameters__efficiency",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    pv_settings_is_selected = models.BooleanField(
        db_column="pv__settings__is_selected",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    pv_settings_design = models.BooleanField(
        db_column="pv__settings__design",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    pv_parameters_nominal_capacity = models.FloatField(
        db_column="pv__parameters__nominal_capacity",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    pv_parameters_lifetime = models.PositiveIntegerField(
        db_column="pv__parameters__lifetime",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    pv_parameters_capex = models.FloatField(
        db_column="pv__parameters__capex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    pv_parameters_opex = models.FloatField(
        db_column="pv__parameters__opex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    rectifier_settings_is_selected = models.BooleanField(
        db_column="rectifier__settings__is_selected",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    rectifier_settings_design = models.BooleanField(
        db_column="rectifier__settings__design",
        default=True,
    )  # Field renamed because it contained more than one '_' in a row.
    rectifier_parameters_nominal_capacity = models.FloatField(
        db_column="rectifier__parameters__nominal_capacity",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    rectifier_parameters_lifetime = models.PositiveIntegerField(
        db_column="rectifier__parameters__lifetime",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    rectifier_parameters_capex = models.FloatField(
        db_column="rectifier__parameters__capex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    rectifier_parameters_opex = models.FloatField(
        db_column="rectifier__parameters__opex",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    rectifier_parameters_efficiency = models.FloatField(
        db_column="rectifier__parameters__efficiency",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    shortage_settings_is_selected = models.FloatField(
        db_column="shortage__settings__is_selected",
        default=False,
    )  # Field renamed because it contained more than one '_' in a row.
    shortage_parameters_max_shortage_total = models.FloatField(
        db_column="shortage__parameters__max_shortage_total",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    shortage_parameters_max_shortage_timestep = models.FloatField(
        db_column="shortage__parameters__max_shortage_timestep",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.
    shortage_parameters_shortage_penalty_cost = models.FloatField(
        db_column="shortage__parameters__shortage_penalty_cost",
        blank=True,
        null=True,
    )  # Field renamed because it contained more than one '_' in a row.

    def to_nested_dict(self):
        nested_dict = lambda: defaultdict(nested_dict)
        data = nested_dict()

        for field in self._meta.fields:
            if field.db_column is not None:
                value = getattr(self, field.name)
                parts = field.db_column.split("__")

                d = data
                for part in parts[:-1]:  # Traverse the dictionary except the last key
                    d = d[part]
                d[parts[-1]] = value  # Set the final value

        return data
