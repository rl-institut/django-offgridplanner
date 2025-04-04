# Generated by Django 5.0.11 on 2025-03-12 11:56

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomDemand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('very_low', models.FloatField(default=0.663)),
                ('low', models.FloatField(default=0.215)),
                ('middle', models.FloatField(default=0.076)),
                ('high', models.FloatField(default=0.031)),
                ('very_high', models.FloatField(default=0.015)),
                ('annual_total_consumption', models.FloatField(blank=True, null=True)),
                ('annual_peak_consumption', models.FloatField(blank=True, null=True)),
                ('project', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to='projects.project')),
            ],
        ),
        migrations.CreateModel(
            name='Energysystemdesign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('battery_settings_is_selected', models.BooleanField(blank=True, db_column='battery__settings__is_selected', null=True)),
                ('battery_settings_design', models.BooleanField(blank=True, db_column='battery__settings__design', null=True)),
                ('battery_parameters_nominal_capacity', models.FloatField(blank=True, db_column='battery__parameters__nominal_capacity', null=True)),
                ('battery_parameters_lifetime', models.PositiveIntegerField(blank=True, db_column='battery__parameters__lifetime', null=True)),
                ('battery_parameters_capex', models.FloatField(blank=True, db_column='battery__parameters__capex', null=True)),
                ('battery_parameters_opex', models.FloatField(blank=True, db_column='battery__parameters__opex', null=True)),
                ('battery_parameters_soc_min', models.FloatField(blank=True, db_column='battery__parameters__soc_min', null=True)),
                ('battery_parameters_soc_max', models.FloatField(blank=True, db_column='battery__parameters__soc_max', null=True)),
                ('battery_parameters_c_rate_in', models.FloatField(blank=True, db_column='battery__parameters__c_rate_in', null=True)),
                ('battery_parameters_c_rate_out', models.FloatField(blank=True, db_column='battery__parameters__c_rate_out', null=True)),
                ('battery_parameters_efficiency', models.FloatField(blank=True, db_column='battery__parameters__efficiency', null=True)),
                ('diesel_genset_settings_is_selected', models.BooleanField(blank=True, db_column='diesel_genset__settings__is_selected', null=True)),
                ('diesel_genset_settings_design', models.BooleanField(blank=True, db_column='diesel_genset__settings__design', null=True)),
                ('diesel_genset_parameters_nominal_capacity', models.FloatField(blank=True, db_column='diesel_genset__parameters__nominal_capacity', null=True)),
                ('diesel_genset_parameters_lifetime', models.PositiveIntegerField(blank=True, db_column='diesel_genset__parameters__lifetime', null=True)),
                ('diesel_genset_parameters_capex', models.FloatField(blank=True, db_column='diesel_genset__parameters__capex', null=True)),
                ('diesel_genset_parameters_opex', models.FloatField(blank=True, db_column='diesel_genset__parameters__opex', null=True)),
                ('diesel_genset_parameters_variable_cost', models.FloatField(blank=True, db_column='diesel_genset__parameters__variable_cost', null=True)),
                ('diesel_genset_parameters_fuel_cost', models.FloatField(blank=True, db_column='diesel_genset__parameters__fuel_cost', null=True)),
                ('diesel_genset_parameters_fuel_lhv', models.FloatField(blank=True, db_column='diesel_genset__parameters__fuel_lhv', null=True)),
                ('diesel_genset_parameters_min_load', models.FloatField(blank=True, db_column='diesel_genset__parameters__min_load', null=True)),
                ('diesel_genset_parameters_max_load', models.FloatField(blank=True, db_column='diesel_genset__parameters__max_load', null=True)),
                ('diesel_genset_parameters_min_efficiency', models.FloatField(blank=True, db_column='diesel_genset__parameters__min_efficiency', null=True)),
                ('diesel_genset_parameters_max_efficiency', models.FloatField(blank=True, db_column='diesel_genset__parameters__max_efficiency', null=True)),
                ('inverter_settings_is_selected', models.BooleanField(blank=True, db_column='inverter__settings__is_selected', null=True)),
                ('inverter_settings_design', models.BooleanField(blank=True, db_column='inverter__settings__design', null=True)),
                ('inverter_parameters_nominal_capacity', models.FloatField(blank=True, db_column='inverter__parameters__nominal_capacity', null=True)),
                ('inverter_parameters_lifetime', models.PositiveIntegerField(blank=True, db_column='inverter__parameters__lifetime', null=True)),
                ('inverter_parameters_capex', models.FloatField(blank=True, db_column='inverter__parameters__capex', null=True)),
                ('inverter_parameters_opex', models.FloatField(blank=True, db_column='inverter__parameters__opex', null=True)),
                ('inverter_parameters_efficiency', models.FloatField(blank=True, db_column='inverter__parameters__efficiency', null=True)),
                ('pv_settings_is_selected', models.BooleanField(blank=True, db_column='pv__settings__is_selected', null=True)),
                ('pv_settings_design', models.BooleanField(blank=True, db_column='pv__settings__design', null=True)),
                ('pv_parameters_nominal_capacity', models.FloatField(blank=True, db_column='pv__parameters__nominal_capacity', null=True)),
                ('pv_parameters_lifetime', models.PositiveIntegerField(blank=True, db_column='pv__parameters__lifetime', null=True)),
                ('pv_parameters_capex', models.FloatField(blank=True, db_column='pv__parameters__capex', null=True)),
                ('pv_parameters_opex', models.FloatField(blank=True, db_column='pv__parameters__opex', null=True)),
                ('rectifier_settings_is_selected', models.BooleanField(blank=True, db_column='rectifier__settings__is_selected', null=True)),
                ('rectifier_settings_design', models.BooleanField(blank=True, db_column='rectifier__settings__design', null=True)),
                ('rectifier_parameters_nominal_capacity', models.FloatField(blank=True, db_column='rectifier__parameters__nominal_capacity', null=True)),
                ('rectifier_parameters_lifetime', models.PositiveIntegerField(blank=True, db_column='rectifier__parameters__lifetime', null=True)),
                ('rectifier_parameters_capex', models.FloatField(blank=True, db_column='rectifier__parameters__capex', null=True)),
                ('rectifier_parameters_opex', models.FloatField(blank=True, db_column='rectifier__parameters__opex', null=True)),
                ('rectifier_parameters_efficiency', models.FloatField(blank=True, db_column='rectifier__parameters__efficiency', null=True)),
                ('shortage_settings_is_selected', models.FloatField(blank=True, db_column='shortage__settings__is_selected', null=True)),
                ('shortage_parameters_max_shortage_total', models.FloatField(blank=True, db_column='shortage__parameters__max_shortage_total', null=True)),
                ('shortage_parameters_max_shortage_timestep', models.FloatField(blank=True, db_column='shortage__parameters__max_shortage_timestep', null=True)),
                ('shortage_parameters_shortage_penalty_cost', models.FloatField(blank=True, db_column='shortage__parameters__shortage_penalty_cost', null=True)),
                ('project', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to='projects.project')),
            ],
        ),
        migrations.CreateModel(
            name='GridDesign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('distribution_cable_lifetime', models.PositiveSmallIntegerField(default=25)),
                ('distribution_cable_capex', models.FloatField(default=10)),
                ('distribution_cable_max_length', models.FloatField(default=50)),
                ('connection_cable_lifetime', models.PositiveSmallIntegerField(default=25)),
                ('connection_cable_capex', models.FloatField(default=4)),
                ('connection_cable_max_length', models.FloatField(default=20)),
                ('pole_lifetime', models.PositiveSmallIntegerField(default=25)),
                ('pole_capex', models.FloatField(default=800)),
                ('pole_max_n_connections', models.PositiveSmallIntegerField(default=5)),
                ('mg_connection_cost', models.FloatField(default=140)),
                ('include_shs', models.BooleanField(default=True)),
                ('shs_max_grid_cost', models.FloatField(blank=True, default=0.6, null=True)),
                ('project', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to='projects.project')),
            ],
        ),
    ]
