from django.urls import path

from . import views
from .views import *

app_name = "optimization"

urlpatterns = [
    path(
        "add_buildings_inside_boundary/<int:proj_id>",
        add_buildings_inside_boundary,
        name="add_buildings_inside_boundary",
    ),
    path(
        "remove_buildings_inside_boundary/<int:proj_id>",
        remove_buildings_inside_boundary,
        name="remove_buildings_inside_boundary",
    ),
    path("consumer_to_db", consumer_to_db, name="consumer_to_db"),
    path("consumer_to_db/<int:proj_id>", consumer_to_db, name="consumer_to_db"),
    path("export_demand/<int:proj_id>", export_demand, name="export_demand"),
    path("import_demand/<int:proj_id>", import_demand, name="import_demand"),
    path("db_links_to_js/<int:proj_id>", db_links_to_js, name="db_links_to_js"),
    path("file_nodes_to_js", file_nodes_to_js, name="file_nodes_to_js"),
    path("db_nodes_to_js", db_nodes_to_js, name="db_nodes_to_js"),
    path("db_nodes_to_js/<int:proj_id>", db_nodes_to_js, name="db_nodes_to_js"),
    path(
        "db_nodes_to_js/<int:proj_id>/<str:markers_only>",
        db_nodes_to_js,
        name="db_nodes_to_js",
    ),
    path(
        "load-demand-plot-data/<int:proj_id>",
        load_demand_plot_data,
        name="load_demand_plot_data",
    ),
    path(
        "load-plot-data/<int:proj_id>/<str:plot_type>",
        load_plot_data,
        name="load_plot_data",
    ),
    path(
        "load-plot-data/<int:proj_id>",
        load_plot_data,
        name="load_plot_data",
    ),
    path("load-results/<int:proj_id>", load_results, name="load_results"),
    path(
        "start_calculation/<int:proj_id>",
        start_calculation,
        name="start_calculation",
    ),
    path(
        "waiting_for_results/<int:proj_id>",
        waiting_for_results,
        name="waiting_for_results",
    ),
    path(
        "process_optimization_results/<int:proj_id>",
        process_optimization_results,
        name="process_optimization_results",
    ),
    path(
        "abort_calculation/<int:proj_id>", abort_calculation, name="abort_calculation"
    ),
    path("osm/roads/", views.osm_roads, name="osm_roads"),
]
