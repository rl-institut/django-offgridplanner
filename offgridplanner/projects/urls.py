from django.urls import path

from .views import *

app_name = "projects"

urlpatterns = [
    path("", home, name="home"),
    path("projects", projects_list, name="projects_list"),
    path("<int:proj_id>", projects_list, name="projects_list"),
    path("duplicate/<int:proj_id>", project_duplicate, name="project_duplicate"),
    path("delete/<int:proj_id>", project_delete, name="project_delete"),
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
]
