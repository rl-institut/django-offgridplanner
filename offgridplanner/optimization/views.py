# TODO maybe link task to project and not to user...

import json
import logging
import os
from collections import defaultdict

import numpy as np

# from jsonview.decorators import json_view
import pandas as pd
from django.core.exceptions import PermissionDenied
from django.forms import model_to_dict
from django.http import JsonResponse
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from config.settings.base import DONE
from config.settings.base import ERROR
from config.settings.base import PENDING
from offgridplanner.optimization.grid import osm_utils
from offgridplanner.optimization.helpers import check_imported_consumer_data
from offgridplanner.optimization.helpers import check_imported_demand_data
from offgridplanner.optimization.helpers import consumer_data_to_file
from offgridplanner.optimization.helpers import convert_file_to_df
from offgridplanner.optimization.helpers import df_to_file
from offgridplanner.optimization.helpers import process_optimization_results
from offgridplanner.optimization.helpers import validate_file_extension
from offgridplanner.optimization.models import Links
from offgridplanner.optimization.models import Nodes
from offgridplanner.optimization.models import Roads
from offgridplanner.optimization.models import Simulation
from offgridplanner.optimization.processing import PreProcessor
from offgridplanner.optimization.requests import optimization_check_status
from offgridplanner.optimization.requests import optimization_server_request
from offgridplanner.optimization.supply.demand_estimation import LOAD_PROFILES
from offgridplanner.optimization.supply.demand_estimation import get_demand_timeseries
from offgridplanner.optimization.tasks import revoke_task
from offgridplanner.projects.models import Project
from offgridplanner.steps.models import CustomDemand

logger = logging.getLogger(__name__)
# @require_http_methods(["POST"])
# def forward_if_no_task_is_pending(request, proj_id=None):
#     if proj_id is not None:
#         project = get_object_or_404(Project, id=proj_id)
#         if project.user.email != request.user.email:
#             raise PermissionDenied
#     if (
#         user.token is not None
#         and len(user.token) > 20
#         and not task_is_finished(user.token)
#     ):
#         res = {"forward": False, "token": user.token}
#     else:
#         res = {"forward": True, "token": ""}
#     return JsonResponse(res)


# TODO should be used as AJAX from map
@require_http_methods(["POST"])
def add_buildings_inside_boundary(request, proj_id):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied

    js_data = json.loads(request.body)
    # js_datapydantic_schema.MapData consists of
    #     boundary_coordinates: list
    #     map_elements: list

    boundary_coordinates = js_data["boundary_coordinates"][0][0]
    df = pd.DataFrame.from_dict(boundary_coordinates).rename(
        columns={"lat": "latitude", "lng": "longitude"},
    )
    if df["latitude"].max() - df["latitude"].min() > float(
        os.environ.get("MAX_LAT_LON_DIST", 0.15),
    ):
        return JsonResponse(
            {
                "executed": False,
                "msg": "The maximum latitude distance selected is too large. "
                "Please select a smaller area.",
            },
        )
    if df["longitude"].max() - df["longitude"].min() > float(
        os.environ.get("MAX_LAT_LON_DIST", 0.15),
    ):
        return JsonResponse(
            {
                "executed": False,
                "msg": "The maximum longitude distance selected is too large. "
                "Please select a smaller area.",
            },
        )
    try:
        data, building_coordinates_within_boundaries = (
            osm_utils.get_consumer_within_boundaries(df)
        )
    except RuntimeError:
        return JsonResponse(
            {
                "executed": False,
                "msg": "An error occurred fetching OpenStreetMap building data. Please try again.",
            },
        )
    if not building_coordinates_within_boundaries:
        return JsonResponse(
            {
                "executed": False,
                "msg": "In the selected area, no buildings could be identified.",
            },
        )
    nodes = defaultdict(list)
    for coordinates in building_coordinates_within_boundaries.values():
        nodes["latitude"].append(round(coordinates[0], 6))
        nodes["longitude"].append(round(coordinates[1], 6))
        nodes["how_added"].append("automatic")
        nodes["node_type"].append("consumer")
        nodes["consumer_type"].append("household")
        nodes["consumer_detail"].append("default")
        nodes["custom_specification"].append("")
        nodes["shs_options"].append(0)
        nodes["is_connected"].append(True)
    # if user.email.split('__')[0] == 'anonymous':
    #     max_consumer = int(os.environ.get("MAX_CONSUMER_ANONYMOUS", 150))
    # else:
    max_consumer = int(os.environ.get("MAX_CONSUMER", 1000))
    if len(nodes["latitude"]) > max_consumer:
        return JsonResponse(
            {
                "executed": False,
                "msg": "You have selected {} consumers. You can select a maximum of {} consumer. "
                "Reduce the number of consumers by selecting a small area, for example.".format(
                    len(data["elements"]),
                    max_consumer,
                ),
            },
        )
    df = pd.DataFrame.from_dict(nodes)
    df["is_connected"] = df["is_connected"]
    df_existing = pd.DataFrame.from_records(js_data["map_elements"])
    df = pd.concat([df_existing, df], ignore_index=True)
    df = df.drop_duplicates(subset=["longitude", "latitude"], keep="first")
    df["shs_options"] = df["shs_options"].fillna(0)
    df["custom_specification"] = df["custom_specification"].fillna("")
    df["is_connected"] = df["is_connected"].fillna(value=True)
    nodes_list = df.to_dict("records")
    return JsonResponse({"executed": True, "msg": "", "new_consumers": nodes_list})


# TODO should be used as AJAX from backend_communication.js
@require_http_methods(["POST"])
def remove_buildings_inside_boundary(
    request,
    proj_id=None,
):  # data: pydantic_schema.MapData
    data = json.loads(request.body)
    df = pd.DataFrame.from_records(data["map_elements"])
    if not df.empty:
        boundaries = (
            pd.DataFrame.from_records(
                data["boundary_coordinates"][0][0],
            )
            .to_numpy()
            .tolist()
        )
        df["inside_boundary"] = osm_utils.are_points_in_boundaries(
            df,
            boundaries=boundaries,
        )
        df = df[df["inside_boundary"] == False]  # noqa: E712
        df = df.drop(columns=["inside_boundary"])
        return JsonResponse({"map_elements": df.to_dict("records")})


@require_http_methods(["POST"])
def add_roads_inside_boundary(request, proj_id):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied

    js_data = json.loads(request.body)
    boundary_coordinates = js_data["boundary_coordinates"][0][0]

    df = pd.DataFrame.from_dict(boundary_coordinates).rename(
        columns={"lat": "latitude", "lng": "longitude"},
    )

    if df["latitude"].max() - df["latitude"].min() > float(
        os.environ.get("MAX_LAT_LON_DIST", 0.15)
    ):
        return JsonResponse(
            {
                "executed": False,
                "msg": "The maximum latitude distance selected is too large.",
            }
        )

    if df["longitude"].max() - df["longitude"].min() > float(
        os.environ.get("MAX_LAT_LON_DIST", 0.15)
    ):
        return JsonResponse(
            {
                "executed": False,
                "msg": "The maximum longitude distance selected is too large.",
            }
        )

    try:
        data, road_geometries = osm_utils.get_roads_within_boundaries(df)
    except RuntimeError:
        return JsonResponse(
            {
                "executed": False,
                "msg": "An error occurred fetching OpenStreetMap roads data. Please try again.",
            },
        )

    if not road_geometries:
        return JsonResponse(
            {
                "executed": False,
                "msg": "In the selected area, no roads could be identified.",
            }
        )

    # roads for JS
    roads_list = []
    for road_id, coords in road_geometries.items():
        roads_list.append(
            {
                "road_id": road_id,
                "coordinates": coords,
                "how_added": "automatic",
                "road_type": "osm",
            }
        )

    return JsonResponse({"executed": True, "msg": "", "new_roads": roads_list})


@require_http_methods(["POST"])
def remove_roads_inside_boundary(request, proj_id):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied

    return JsonResponse({"executed": True, "msg": "Roads removed"})


# TODO this seems like an old unused view
@require_http_methods(["GET"])
def db_links_to_js(request, proj_id):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied
        links_qs = Links.objects.filter(project=project)
        links = links_qs.get() if links_qs.exists() else None
        links_json = json.loads(links.data) if links is not None else json.loads("{}")
        return JsonResponse(links_json, status=200)


# @json_view
@require_http_methods(["GET"])
def db_nodes_to_js(request, proj_id=None, *, markers_only=False):
    if isinstance(markers_only, str):
        markers_only = True if markers_only == "true" else False  # noqa:SIM210
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied
        nodes_qs = Nodes.objects.filter(project=project)
        df = nodes_qs.get().df if nodes_qs.exists() else pd.DataFrame()
        is_load_center = True
        if not df.empty:
            df = df[
                [
                    "latitude",
                    "longitude",
                    "how_added",
                    "node_type",
                    "consumer_type",
                    "consumer_detail",
                    "custom_specification",
                    "is_connected",
                    "shs_options",
                ]
            ]
            power_house = df[df["node_type"] == "power-house"]
            if markers_only is True:
                if (
                    len(power_house) > 0
                    and power_house["how_added"].iloc[0] == "manual"
                ):
                    df = df[df["node_type"].isin(["power-house", "consumer"])]
                else:
                    df = df[df["node_type"] == "consumer"]
            df = df.fillna("null")
            if (
                len(power_house.index) > 0
                and power_house["how_added"].iloc[0] == "manual"
            ):
                is_load_center = False

        nodes_list = df.to_dict("records")
        return JsonResponse(
            {"is_load_center": is_load_center, "map_elements": nodes_list},
            status=200,
        )
    return JsonResponse({"msg": "Missing project ID"}, status=400)


@require_http_methods(["GET"])
def db_roads_to_js(request, proj_id=None):
    project = get_object_or_404(Project, id=proj_id)
    try:
        roads = Roads.objects.get(project=project)
        data = json.loads(roads.data) if isinstance(roads.data, str) else roads.data
        return JsonResponse({"road_elements": data})
    except Roads.DoesNotExist:
        return JsonResponse({"road_elements": []})


@require_http_methods(["POST"])
def consumer_to_db(request, proj_id=None):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied

        data = json.loads(request.body)
        map_elements = data.get("map_elements", [])
        file_type = data.get("file_type", "")

        if not map_elements:
            Nodes.objects.filter(project=project).delete()
            return JsonResponse({"message": "No data provided"}, status=200)

        # Create DataFrame and clean data
        df = pd.DataFrame.from_records(map_elements)

        if df.empty:
            Nodes.objects.filter(project=project).delete()
            return JsonResponse({"message": "No valid data"}, status=200)

        df = df.drop_duplicates(subset=["latitude", "longitude"])
        df = df[df["node_type"].isin(["power-house", "consumer"])]

        # Ensure only one power-house node remains
        df = df.drop(df[df["node_type"] == "power-house"].index[1:], errors="ignore")

        # Keep only relevant columns
        required_columns = [
            "latitude",
            "longitude",
            "how_added",
            "node_type",
            "consumer_type",
            "custom_specification",
            "shs_options",
            "consumer_detail",
        ]
        df = df[required_columns]

        # Fill missing values
        df["consumer_type"] = df["consumer_type"].fillna("household")
        df["custom_specification"] = df["custom_specification"].fillna("")
        df["shs_options"] = df["shs_options"].fillna(0)
        df["is_connected"] = True
        df["node_type"] = df["node_type"].astype(str)

        # Format latitude and longitude
        df["latitude"] = df["latitude"].map(lambda x: f"{x:.6f}")
        df["longitude"] = df["longitude"].map(lambda x: f"{x:.6f}")

        # Handle optional 'parent' column
        if "parent" in df.columns:
            df["parent"] = df["parent"].replace("unknown", None)

        if file_type == "db":
            nodes, _ = Nodes.objects.get_or_create(project=project)
            nodes.data = df.to_json(orient="records")  # Keep format structured
            nodes.save()
            return JsonResponse({"message": "Success"}, status=200)

        # Handle file downloads
        io_file = consumer_data_to_file(df, file_type)
        response = StreamingHttpResponse(io_file)

        if file_type == "xlsx":
            response.headers["Content-Disposition"] = (
                "attachment; filename=offgridplanner_consumers.xlsx"
            )
        elif file_type == "csv":
            response.headers["Content-Disposition"] = (
                "attachment; filename=offgridplanner_consumers.csv"
            )

        return response


@require_http_methods(["POST"])
def roads_to_db(request, proj_id=None):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied

        data = json.loads(request.body)
        road_elements = data.get("road_elements", [])

        if not road_elements:
            Roads.objects.filter(project=project).delete()
            return JsonResponse({"message": "No data provided"}, status=200)

        df = pd.DataFrame.from_records(road_elements)
        if df.empty:
            Roads.objects.filter(project=project).delete()
            return JsonResponse({"message": "No valid data"}, status=200)

        df = df.drop_duplicates(subset=["road_id"], keep="first")
        required_columns = ["road_id", "coordinates", "how_added", "road_type"]
        df = df[required_columns]
        df["how_added"] = df["how_added"].fillna("automatic")
        df["road_type"] = df["road_type"].fillna("osm")

        roads, _ = Roads.objects.get_or_create(project=project)

        roads.data = df.to_json(orient="records")
        roads.save()

        return JsonResponse({"message": "Success"}, status=200)

    return JsonResponse({"error": "Project ID missing"}, status=400)


@require_http_methods(["POST"])
def file_nodes_to_js(request, proj_id):
    if "file" not in request.FILES:
        return JsonResponse({"responseMsg": "No file uploaded."}, status=400)

    file = request.FILES["file"]
    is_valid, result = validate_file_extension(file.name)

    if not is_valid:
        return JsonResponse({"responseMsg": result}, status=400)

    file_extension = result
    df = convert_file_to_df(file, file_extension)

    try:
        df, msg = check_imported_consumer_data(df, proj_id)
        if df is None and msg:
            return JsonResponse({"responseMsg": msg}, status=400)
    except ValueError as e:
        return JsonResponse(
            {"responseMsg": f"Failed to validate data: {e!s}"}, status=400
        )

    return JsonResponse(
        data={"is_load_center": False, "map_elements": df.to_dict("records")},
        status=200,
    )


def load_demand_plot_data(request, proj_id=None):
    # if is_ajax(request):
    time_range = range(24)
    nodes = Nodes.objects.get(project__id=proj_id)
    custom_demand = CustomDemand.objects.get(project__id=proj_id)
    # get demand and convert to kWh
    demand_df = (
        get_demand_timeseries(nodes, custom_demand, time_range=time_range) / 1000
    )
    load_profiles = LOAD_PROFILES.iloc[time_range].copy()

    timeseries = {
        "x": demand_df.index.tolist(),
        "households": demand_df.household.tolist(),
        "enterprises": demand_df.enterprise.tolist(),
        "public_services": demand_df.public_service.tolist(),
        "Average": np.zeros(len(time_range)),
    }

    for tier in ["very_low", "low", "middle", "high", "very_high"]:
        tier_verbose = f"{tier.title().replace('_', ' ')} Consumption"
        profile_col = f"Household_Distribution_Based_{tier_verbose}"
        timeseries[tier_verbose] = load_profiles[profile_col].to_numpy().tolist()
        timeseries["Average"] = np.add(
            getattr(custom_demand, tier)
            * np.array(load_profiles[profile_col].to_numpy().tolist()),
            timeseries["Average"],
        )

    timeseries["Average"] = timeseries["Average"].tolist()
    return JsonResponse({"timeseries": timeseries})


def export_demand(request, proj_id):
    project = Project.objects.get(id=proj_id)
    data = json.loads(request.body)
    file_type = data["file_type"]
    total_demand = get_demand_timeseries(
        project.nodes, project.customdemand, time_range=range(project.n_days * 24)
    ).sum(axis=1)
    total_demand_df = total_demand.reset_index()
    total_demand_df.columns = ["timestamp", "demand"]

    io_file = df_to_file(total_demand_df, file_type)
    response = StreamingHttpResponse(io_file)

    response.headers["Content-Disposition"] = (
        f"attachment; filename=offgridplanner_demand.{file_type}"
    )

    return response


def import_demand(request, proj_id):
    file = request.FILES["file"]
    project = Project.objects.get(id=proj_id)
    is_valid, result = validate_file_extension(file.name)

    if not is_valid:
        return JsonResponse({"responseMsg": result}, status=400)

    file_extension = result

    df = convert_file_to_df(file, file_extension)
    project_dict = model_to_dict(project)

    df, error_msg = check_imported_demand_data(df, project_dict)
    if df is None:
        return JsonResponse({"responseMsg": error_msg}, status=400)

    custom_demand = project.customdemand
    custom_demand.uploaded_data = df.to_json()
    custom_demand.save()

    return JsonResponse({"responseMsg": ""})


def load_plot_data(request, proj_id, plot_type=None):
    project = Project.objects.get(id=proj_id)
    if plot_type == "energy_flow":
        energy_flow = project.energyflow.df
        energy_flow["battery"] = (
            energy_flow["battery_discharge"] - energy_flow["battery_charge"]
        )
        energy_flow = energy_flow.drop(columns=["battery_charge", "battery_discharge"])
        energy_flow = energy_flow.reset_index(drop=True)
        energy_flow = energy_flow.dropna(how="all", axis=0).fillna(0).to_dict("list")
        return JsonResponse({"energy_flow": energy_flow})
    elif plot_type == "duration_curve":
        duration_curve = project.durationcurve.df
        duration_curve = (
            duration_curve.dropna(how="all", axis=0).fillna(0).to_dict("list")
        )
        return JsonResponse({"duration_curve": duration_curve})
    elif plot_type == "emissions":
        emissions = project.emissions.df
        emissions = emissions.dropna(how="all", axis=0).fillna(0).to_dict("list")
        return JsonResponse({"emissions": emissions})
    elif plot_type == "demand_coverage":
        demand_coverage = project.demandcoverage.df
        demand_coverage = (
            demand_coverage.dropna(how="all", axis=0).fillna(0).to_dict("list")
        )
        return JsonResponse({"demand_coverage": demand_coverage})
    elif plot_type == "other":
        res = project.simulation.results
        df = pd.Series(model_to_dict(res)).astype(str)
        optimal_capacity_keys = [
            "pv",
            "battery",
            "inverter",
            "rectifier",
            "diesel_genset",
            "peak_demand",
            "surplus",
        ]
        optimal_capacities = {
            key: df[f"{key}_capacity"] for key in optimal_capacity_keys[:-2]
        }
        optimal_capacities.update({key: df[key] for key in optimal_capacity_keys[-2:]})
        lcoe_breakdown_keys = [
            "renewable_assets",
            "non_renewable_assets",
            "grid",
            "fuel",
        ]
        lcoe_breakdown = {key: df[f"cost_{key}"] for key in lcoe_breakdown_keys}

        sankey_keys = [
            "fuel_to_diesel_genset",
            "diesel_genset_to_rectifier",
            "diesel_genset_to_demand",
            "rectifier_to_dc_bus",
            "pv_to_dc_bus",
            "battery_to_dc_bus",
            "dc_bus_to_battery",
            "dc_bus_to_inverter",
            "dc_bus_to_surplus",
            "inverter_to_demand",
        ]
        sankey_data = {key: df[key] for key in sankey_keys}
        return JsonResponse(
            {
                "optimal_capacities": optimal_capacities,
                "lcoe_breakdown": lcoe_breakdown,
                "sankey_data": sankey_data,
            }
        )
    else:
        return JsonResponse({"msg": "Plot type undefined"}, status=400)


@require_http_methods(["POST"])
def start_calculation(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)
    opts = project.options
    simulation = project.simulation
    # TODO set up redirect later if we keep this
    # forward, redirect = await async_queries.check_data_availability(user.id, project_id)
    # if forward is False:
    #     return JsonResponse({'token': '', 'redirect': redirect})
    preprocessor = PreProcessor(proj_id)
    supply_opt_json = preprocessor.collect_supply_opt_json_data()
    grid_opt_json = preprocessor.collect_grid_opt_json_data()
    try:
        token_grid = (
            optimization_server_request(grid_opt_json, "grid")["id"]
            if opts.do_grid_optimization
            else ""
        )
        token_supply = (
            optimization_server_request(supply_opt_json, "supply")["id"]
            if opts.do_es_design_optimization
            else ""
        )

    except RuntimeError as e:
        logger.exception("Error getting optimization tokens")
        return JsonResponse(
            {
                "error": "There was an error with the simulation request. Hint: check the server connection and/or the outgoing JSON format"
            },
            status=500,
        )

    simulation.token_grid = token_grid
    simulation.token_supply = token_supply
    simulation.save()

    return JsonResponse({"token_supply": token_supply, "token_grid": token_grid})


# async def check_data_availability(user_id, project_id):
# TODO checks data availability and redirects the user if missing - not sure we want to keep this
# project_setup = await get_model_instance(sa_tables.ProjectSetup, user_id, project_id)
# if project_setup is None:
#     return False, '/project_setup/?project_id=' + str(project_id)
# nodes = await get_model_instance(sa_tables.Nodes, user_id, project_id)
# nodes_df = pd.read_json(nodes.data) if nodes is not None else None
# if nodes_df is None or nodes_df.empty or nodes_df[nodes_df['node_type'] == 'consumer'].index.__len__() == 0:
#     if project_setup.do_demand_estimation and project_setup.do_es_design_optimization:
#         return False, '/consumer_selection/?project_id=' + str(project_id)
# demand_opt_dict = await get_model_instance(sa_tables.Demand, user_id, project_id)
# if demand_opt_dict is None or pd.isna(demand_opt_dict.household_option):
#     return False, '/demand_estimation/?project_id=' + str(project_id)
# if project_setup.do_grid_optimization is True:
#     grid_design = await get_model_instance(sa_tables.GridDesign, user_id, project_id)
#     if grid_design is None or pd.isna(grid_design.pole_lifetime):
#         return False, '/grid_design/?project_id=' + str(project_id)
# if project_setup.do_es_design_optimization is True:
#     energy_system_design = await get_model_instance(sa_tables.EnergySystemDesign, user_id, project_id)
#     if energy_system_design is None or pd.isna(energy_system_design.battery__parameters__c_rate_in):
#         return False, '/energy_system_design/?project_id=' + str(project_id)
# return True, None


@require_http_methods(["POST"])
def waiting_for_results(request, proj_id):
    data = json.loads(request.body)

    token = data["token"]
    model = data["model"]
    total_time = data["time"]
    results = None
    # TODO handle wait time between sim checks
    wait_time = 3

    # Fetch the right simulation object
    if model == "grid":
        simulation = get_object_or_404(Simulation, token_grid=token)
    else:
        simulation = get_object_or_404(Simulation, token_supply=token)

    # Check the optimization server
    response = optimization_check_status(token=token)
    status = response.get("status") if response is not None else ERROR
    print(f"{model} {status}")
    if status not in [DONE, ERROR, PENDING]:
        logger.warning("Simulation returned unexpected status")

    if status == DONE:
        try:
            model = response.get("server_info")
            server_results = response.get("results")
            results = server_results
            logger.info("Simulation finished")
        except Exception:
            logger.exception("Error parsing results")
            status = ERROR
    elif status == ERROR:
        try:
            results = json.dumps(response.get("results", {}).get(ERROR))
        except AttributeError:
            results = None
        logger.warning("Simulation failed with errors.")

    # Update simulation status
    if model == "grid":
        simulation.status_grid = status
    else:
        simulation.status_supply = status
    simulation.save()
    return JsonResponse(
        {
            "token": token,
            "model": model,
            "time": total_time + wait_time,
            "status": status,
            "finished": status != PENDING,
            "results": results,
        }
    )


def handle_optimization_results_request(request, proj_id):
    # Processes the results (contains both optimization result objects)
    data = json.loads(request.body)
    sim_res = data.get("results", {})
    process_optimization_results(proj_id, sim_res)
    return JsonResponse({"msg": "Optimization results saved to database"})


def abort_calculation(request, proj_id):
    # TODO send an abort request to the simulation server
    simulation = Simulation.objects.get(project=proj_id)
    token = simulation.token
    revoke_task(token)
    simulation.token = ""
    simulation.save()
    response = {"msg": "Calculation aborted"}
    return JsonResponse(response)
