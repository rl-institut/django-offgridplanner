from django.urls import path

from .views import *

app_name = "steps"

urlpatterns = [
    path("<int:proj_id>/edit/step/<int:step_id>", steps, name="ogp_steps"),
    path("project_setup", project_setup, name="project_setup"),
    path("project_setup/<int:proj_id>", project_setup, name="project_setup"),
    path('project/<int:proj_id>/bounds/', get_project_bounds, name='project_bounds'), # Bachirou
    path("consumer_selection", consumer_selection, name="consumer_selection"),
    path(
        "consumer_selection/<int:proj_id>",
        consumer_selection,
        name="consumer_selection",
    ),
    path("demand_estimation", demand_estimation, name="demand_estimation"),
    path(
        "demand_estimation/<int:proj_id>",
        demand_estimation,
        name="demand_estimation",
    ),
    path("grid_design", grid_design, name="grid_design"),
    path("grid_design/<int:proj_id>", grid_design, name="grid_design"),
    path("energy_system_design", energy_system_design, name="energy_system_design"),
    path(
        "energy_system_design/<int:proj_id>",
        energy_system_design,
        name="energy_system_design",
    ),
    path("calculating", calculating, name="calculating"),
    path("calculating/<int:proj_id>", calculating, name="calculating"),
    path("simulation_results", simulation_results, name="simulation_results"),
    path(
        "simulation_results/<int:proj_id>",
        simulation_results,
        name="simulation_results",
    ),
]
