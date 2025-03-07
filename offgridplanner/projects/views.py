import io
import json
import os
import time
from collections import defaultdict

import numpy as np

# from jsonview.decorators import json_view
import pandas as pd
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.forms import model_to_dict
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from offgridplanner.projects import identify_consumers_on_map
from offgridplanner.projects.demand_estimation import LOAD_PROFILES
from offgridplanner.projects.demand_estimation import get_demand_timeseries
from offgridplanner.projects.helpers import check_imported_consumer_data
from offgridplanner.projects.helpers import consumer_data_to_file
from offgridplanner.projects.helpers import load_project_from_dict
from offgridplanner.projects.models import CustomDemand
from offgridplanner.projects.models import Energysystemdesign
from offgridplanner.projects.models import GridDesign
from offgridplanner.projects.models import Nodes
from offgridplanner.projects.models import Options
from offgridplanner.projects.models import Project
from offgridplanner.projects.models import Simulation
from offgridplanner.projects.tasks import get_status
from offgridplanner.projects.tasks import hello
from offgridplanner.projects.tasks import task_grid_opt
from offgridplanner.projects.tasks import task_is_finished
from offgridplanner.projects.tasks import task_supply_opt
from offgridplanner.users.models import User


# @login_required
@require_http_methods(["GET"])
def projects_list(request, proj_id=None):
    projects = (
        Project.objects.filter(Q(user=request.user))
        .distinct()
        .order_by("date_created")
        .reverse()
    )
    for project in projects:
        # TODO this should not be useful
        # project.created_at = project.created_at.date()
        # project.updated_at = project.updated_at.date()
        if bool(os.environ.get("DOCKERIZED")):
            status = "pending"  # TODO connect this to the worker
            # status = worker.AsyncResult(user.task_id).status.lower()
        else:
            status = "success"
        if status in ["success", "failure", "revoked"]:
            # TODO this is not useful
            # user.task_id = ''
            # user.project_id = None
            if status == "success":
                # TODO Here I am not sure we should use the status of the project rather the one of the simulation
                project.status = "finished"
            else:
                project.status = status
            project.save()
            # TODO this is not useful
            # user.task_id = ''
            # user.project_id = None

    return render(request, "pages/user_projects.html", {"projects": projects})


@require_http_methods(["GET", "POST"])
def project_duplicate(request, proj_id):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied
        # TODO check user rights to the project
        dm = project.export()
        user = User.objects.get(email=request.user.email)
        # TODO must find user from its email address
        new_proj_id = load_project_from_dict(dm, user=user)

    return HttpResponseRedirect(reverse("projects:projects_list"))


@require_http_methods(["POST"])
def project_delete(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)

    if project.user != request.user:
        raise PermissionDenied

    if request.method == "POST":
        project.delete()
        # message not defined
        messages.success(request, "Project successfully deleted!")

    return HttpResponseRedirect(reverse("projects:projects_list"))


# TODO maybe link task to project and not to user...
@require_http_methods(["POST"])
def forward_if_no_task_is_pending(request, proj_id=None):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user.email != request.user.email:
            raise PermissionDenied
    if (
        user.task_id is not None
        and len(user.task_id) > 20
        and not task_is_finished(user.task_id)
    ):
        res = {"forward": False, "task_id": user.task_id}
    else:
        res = {"forward": True, "task_id": ""}
    return JsonResponse(res)


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
    data, building_coordinates_within_boundaries = (
        identify_consumers_on_map.get_consumer_within_boundaries(df)
    )
    if not building_coordinates_within_boundaries:
        return JsonResponse(
            {
                "executed": False,
                "msg": "In the selected area, no buildings could be identified.",
            },
        )
    nodes = defaultdict(list)
    for label, coordinates in building_coordinates_within_boundaries.items():
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
    df["is_connected"] = df["is_connected"].fillna(True)
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
        boundaries = pd.DataFrame.from_records(
            data["boundary_coordinates"][0][0],
        ).values.tolist()
        df["inside_boundary"] = identify_consumers_on_map.are_points_in_boundaries(
            df,
            boundaries=boundaries,
        )
        df = df[df["inside_boundary"] == False]
        df = df.drop(columns=["inside_boundary"])
        return JsonResponse({"map_elements": df.to_dict("records")})


# TODO this seems like an old unused view
@require_http_methods(["GET"])
def db_links_to_js(request, proj_id):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied
        # links = Links.objects.filter(project=project).first()
        links = None
        links_json = json.loads(links.data) if links is not None else json.loads("{}")
        return JsonResponse(links_json, status=200)


# @json_view
@require_http_methods(["GET"])
def db_nodes_to_js(request, proj_id=None, markers_only=False):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied
        nodes = get_object_or_404(Nodes, project=project)
        df = nodes.df if nodes is not None else pd.DataFrame()
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
                if len(power_house) > 0 and power_house["how_added"].iat[0] == "manual":
                    df = df[df["node_type"].isin(["power-house", "consumer"])]
                else:
                    df = df[df["node_type"] == "consumer"]
            df["latitude"] = df["latitude"].astype(float)
            df["longitude"] = df["longitude"].astype(float)
            df["shs_options"] = df["shs_options"].fillna(0)
            df["custom_specification"] = df["custom_specification"].fillna("")
            df["shs_options"] = df["shs_options"].astype(int)
            df["is_connected"] = df["is_connected"].astype(bool)
            nodes_list = df.to_dict("records")
            is_load_center = True
            if (
                len(power_house.index) > 0
                and power_house["how_added"].iat[0] == "manual"
            ):
                is_load_center = False
            return JsonResponse(
                {"is_load_center": is_load_center, "map_elements": nodes_list},
                status=200,
            )


@require_http_methods(["POST"])
# async def consumer_to_db(request, proj_id):
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
# async def file_nodes_to_js(file):  # UploadFile = File(...)
def file_nodes_to_js(request):  # UploadFile = File(...)
    file = request.FILES["file"]
    filename = file.name
    file_extension = filename.split(".")[-1].lower()
    if file_extension not in ["csv", "xlsx"]:
        raise HttpResponse(
            status=400,
            reason="Unsupported file type. Please upload a CSV or Excel file.",
        )
    try:
        if file_extension == "csv":
            file_content = file.read()
            # file_content = await file.read()
            decoded_content = file_content.decode("utf-8")
            df = pd.read_csv(io.StringIO(decoded_content))
        elif file_extension == "xlsx":
            df = pd.read_excel(io.BytesIO(file.read()), engine="openpyxl")
            # df = pd.read_excel(io.BytesIO(await file.read()), engine='openpyxl')
        if not df.empty:
            print(df)
            try:
                df, msg = check_imported_consumer_data(df)
                if df is None and msg is not None:
                    return JsonResponse({"responseMsg": msg}, status=200)
            except Exception as e:
                err_msg = str(e)
                msg = f"Failed to import file. Internal error message: {err_msg}"
                return JsonResponse({"responseMsg": msg}, status=200)
            return JsonResponse(
                data={"is_load_center": False, "map_elements": df.to_dict("records")},
                status=200,
            )
    except Exception as e:
        raise HttpResponse(status=500, reason=f"Failed to process the file: {e}")


def load_demand_plot_data(request, proj_id=None):
    # if is_ajax(request):
    time_range = range(24)
    nodes = Nodes.objects.get(project__id=proj_id)
    custom_demand = CustomDemand.objects.get(project__id=proj_id)
    demand_df = get_demand_timeseries(nodes, custom_demand, time_range=time_range)
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
        timeseries[tier_verbose] = load_profiles[profile_col].values.tolist()
        timeseries["Average"] = np.add(
            getattr(custom_demand, tier)
            * np.array(load_profiles[profile_col].values.tolist()),
            timeseries["Average"],
        )

    timeseries["Average"] = timeseries["Average"].tolist()
    return JsonResponse({"timeseries": timeseries}, status=200)


def start_calculation(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)

    simulation = project.simulation
    # TODO set up redirect later if we keep this
    # forward, redirect = await async_queries.check_data_availability(user.id, project_id)
    # if forward is False:
    #     return JsonResponse({'task_id': '', 'redirect': redirect})
    task_id = optimization(proj_id)
    simulation.task_id = task_id
    simulation.save()

    return JsonResponse({"task_id": task_id, "redirect": ""})


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


def optimization(proj_id):
    project = get_object_or_404(Project, id=proj_id)
    opts = project.options
    simulation = Simulation.objects.get(project=project)
    simulation.status = "queued"
    simulation.save()
    if opts.do_grid_optimization is True:
        task = task_grid_opt.delay(proj_id)
    else:
        task = task_supply_opt.delay(proj_id)
    return task.id


def waiting_for_results(request):
    body_unicode = request.body.decode("utf-8")
    data = json.loads(body_unicode)
    total_time = data["time"]
    task_id = data["task_id"]
    model = data["model"]
    finished = False
    wait_time = 10

    status = get_status(task_id)

    if task_is_finished(task_id):
        print(f"Task {model} optimization finished")
        sim = Simulation.objects.get(task_id=task_id)
        project = sim.project

        # Grid opt is finished, proceed to supply opt
        if model == "grid" and project.options.do_es_design_optimization:
            # TODO for testing purposes while supply_opt is not ready, fix later
            # new_task = task_supply_opt.delay(project.id)
            new_task = hello.delay()
            sim.task_id = new_task.id
            sim.save()
            finished = False
            model = "supply"
            status = "power supply optimization is running..."
            task_id = new_task.id

        # Supply opt is finished
        else:
            sim.status = (
                "finished" if status in ["success", "failure", "revoked"] else status
            )
            # TODO: decide whether to keep or clear task_id
            # sim.task_id = None
            sim.save()
            finished = True
            status = sim.status
    else:
        print(f"Task {model} optimization pending")
        # If the task is still running, retry after a calculated delay
        time.sleep(wait_time)
        total_time += wait_time

    # Prepare response structure
    response = {
        "time": total_time,
        "status": status,
        "task_id": task_id,
        "model": model,
        "finished": finished,
    }
    return JsonResponse(response)


def get_project_data(project):
    # TODO in the original function the user is redirected to whatever page has missing data, i would rather do an error message
    """
    Checks if all necessary data for the optimization exists
    :param project:
    :return:
    """
    options = Options.objects.get(project=project)

    model_qs = {
        "Nodes": Nodes.objects.filter(project=project),
        "CustomDemand": CustomDemand.objects.filter(project=project),
        "GridDesign": GridDesign.objects.filter(project=project),
        "Energysystemdesign": Energysystemdesign.objects.filter(project=project),
    }

    # TODO check which models are only necessary for the skipped steps and exclude them
    if options.do_demand_estimation is False:
        # qs.pop(..)
        pass

    if options.do_grid_optimization is False:
        pass

    if options.do_es_design_optimization is False:
        pass

    missing_qs = [key for key, qs in model_qs.items() if not qs.exists()]
    if missing_qs:
        raise ValueError(
            f"The project does not contain all data required for the optimization."
            f" The following models are missing: {missing_qs}",
        )
    proj_data = {key: qs.get() for key, qs in model_qs.items()}
    return proj_data


def load_results(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)
    opts = project.options
    res = project.simulation.results
    df = pd.Series(model_to_dict(res))
    # TODO delete
    df.fillna(0.1, inplace=True)
    infeasible = bool(df["infeasible"]) if "infeasible" in df else False
    if df.empty:
        return JsonResponse({})
    # TODO figure out this logic - I changed it so it would run through but it doesnt make so much sense to me
    # if df['lcoe'] is None and opts.do_es_design_optimization is True:
    #     return JsonResponse({})
    # elif df['n_poles']is None and opts.do_grid_optimization is True:
    #     return JsonResponse({})
    if opts.do_grid_optimization is True:
        df["average_length_distribution_cable"] = (
            df["length_distribution_cable"] / df["n_distribution_links"]
        )
        df["average_length_connection_cable"] = (
            df["length_connection_cable"] / df["n_connection_links"]
        )
        df["gridLcoe"] = float(df["cost_grid"]) / float(df["epc_total"]) * 100
    else:
        df["average_length_distribution_cable"] = None
        df["average_length_connection_cable"] = None
        df["gridLcoe"] = 0
    df[["time_grid_design", "time_energy_system_design"]] = df[
        ["time_grid_design", "time_energy_system_design"]
    ].fillna(0)
    df["time"] = df["time_grid_design"] + df["time_energy_system_design"]
    unit_dict = {
        "n_poles": "",
        "n_consumers": "",
        "n_shs_consumers": "",
        "length_distribution_cable": "m",
        "average_length_distribution_cable": "m",
        "length_connection_cable": "m",
        "average_length_connection_cable": "m",
        "cost_grid": "USD/a",
        "lcoe": "",
        "gridLcoe": "%",
        "esLcoe": "%",
        "res": "%",
        "max_voltage_drop": "%",
        "shortage_total": "%",
        "surplus_rate": "%",
        "time": "s",
        "co2_savings": "t/a",
        "total_annual_consumption": "kWh/a",
        "average_annual_demand_per_consumer": "W",
        "upfront_invest_grid": "USD",
        "upfront_invest_diesel_gen": "USD",
        "upfront_invest_inverter": "USD",
        "upfront_invest_rectifier": "USD",
        "upfront_invest_battery": "USD",
        "upfront_invest_pv": "USD",
        "upfront_invest_converters": "USD",
        "upfront_invest_total": "USD",
        "battery_capacity": "kWh",
        "pv_capacity": "kW",
        "diesel_genset_capacity": "kW",
        "inverter_capacity": "kW",
        "rectifier_capacity": "kW",
        "co2_emissions": "t/a",
        "fuel_consumption": "liter/a",
        "peak_demand": "kW",
        "base_load": "kW",
        "max_shortage": "%",
        "cost_fuel": "USD/a",
        "epc_pv": "USD/a",
        "epc_diesel_genset": "USD/a",
        "epc_inverter": "USD/a",
        "epc_rectifier": "USD/a",
        "epc_battery": "USD/a",
        "epc_total": "USD/a",
    }
    if opts.do_es_design_optimization is True:
        df["esLcoe"] = (
            (float(df["epc_total"]) - float(df["cost_grid"]))
            / float(df["epc_total"])
            * 100
        )
        if int(df["n_consumers"]) != int(df["n_shs_consumers"]) and not infeasible:
            df["upfront_invest_converters"] = sum(
                df[col] for col in df.columns if "upfront" in col and "grid" not in col
            )
            df["upfront_invest_total"] = (
                df["upfront_invest_converters"] + df["upfront_invest_grid"]
            )
        else:
            df["upfront_invest_converters"] = None
            df["upfront_invest_total"] = None
    else:
        df["upfront_invest_converters"] = None
        df["upfront_invest_total"] = None
        df["esLcoe"] = 0
    df = df[list(unit_dict.keys())].round(1).astype(str)
    # TODO formatting, figure out later
    # for col in df.keys():
    #     if unit_dict[col] in ['%', 's', 'kW', 'kWh']:
    #         df[col] = df[col].where(df[col] != 'None', 0)
    #         if df[col].isna().sum() == 0:
    #             df[col] = df[col].astype(float).round(1).astype(str)
    #     elif unit_dict[col] in ['USD', 'kWh/a', 'USD/a']:
    #         if df[col].isna().sum() == 0 and df.loc[0, col] != 'None':
    #             df[col] = "{:,}".format(df[col].astype(float).astype(int).iat[0])
    #     df[col] = df[col] + ' ' + unit_dict[col]
    df["do_grid_optimization"] = opts.do_grid_optimization
    df["do_es_design_optimization"] = opts.do_es_design_optimization
    results = df.to_dict()
    if infeasible is True:
        results["responseMsg"] = (
            "There are no results of the energy system optimization. There were no feasible "
            "solution."
        )
    elif int(results["n_consumers"]) == int(results["n_shs_consumers"]):
        results["responseMsg"] = (
            "Due to high grid costs, all consumers have been equipped with solar home "
            "systems. A grid was not built, therefore no optimization of the energy system was "
            "carried out."
        )
    else:
        results["responseMsg"] = ""
    return JsonResponse(results, status=200)


# TODO define later based on results models - could also be a method in the results model
def remove_results(user_id, project_id):
    # await remove(sa_tables.Results, user_id, project_id)
    # await remove(sa_tables.DemandCoverage, user_id, project_id)
    # await remove(sa_tables.EnergyFlow, user_id, project_id)
    # await remove(sa_tables.Emissions, user_id, project_id)
    # await remove(sa_tables.DurationCurve, user_id, project_id)
    # await remove(sa_tables.Links, user_id, project_id)
    pass
