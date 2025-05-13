from django.urls import path

from .views import *

app_name = "projects"

urlpatterns = [
    path("", home, name="home"),
    path("projects", projects_list, name="projects_list"),
    path("projects/<str:status>", projects_list, name="projects_list"),
    path("<int:proj_id>", projects_list, name="projects_list"),
    path("duplicate/<int:proj_id>", project_duplicate, name="project_duplicate"),
    path("delete/<int:proj_id>", project_delete, name="project_delete"),
    path("update_project_status", update_project_status, name="update_project_status"),
    path(
        "export_results/<int:proj_id>",
        export_project_results,
        name="export_project_results",
    ),
    path(
        "export_report/<int:proj_id>",
        export_project_report,
        name="export_project_report",
    ),
    path("projects/potential/map/", potential_map, name="potential_map"),
    path("api/locations/", locations_geojson, name="locations_geojson"),
    path("ajax/filter_locations/", filter_locations, name="filter_locations"),
]
