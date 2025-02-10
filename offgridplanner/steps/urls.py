from django.urls import path

from .views import *

app_name = "steps"

urlpatterns = [
    path("<int:proj_id>/edit/step/<int:step_id>", steps, name="ogp_steps"),
    path("project_setup", project_setup, name="project_setup"),
    path("project_setup/<int:proj_id>", project_setup, name="project_setup"),
    path("consumer_selection", consumer_selection, name="consumer_selection"),
    path("demand_estimation", demand_estimation, name="demand_estimation"),
    path("grid_design", grid_design, name="grid_design"),
    path("energy_system_design", energy_system_design, name="energy_system_design"),
    path("simulation_results", simulation_results, name="simulation_results"),
]
