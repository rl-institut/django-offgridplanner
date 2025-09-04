import io
import json

# from jsonview.decorators import json_view
import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.forms import model_to_dict
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from offgridplanner.optimization.models import Links
from offgridplanner.optimization.models import Nodes
from offgridplanner.optimization.requests import fetch_existing_minigrids
from offgridplanner.optimization.requests import fetch_exploration_progress
from offgridplanner.optimization.requests import fetch_potential_minigrid_data
from offgridplanner.optimization.requests import start_site_exploration
from offgridplanner.optimization.requests import stop_site_exploration
from offgridplanner.projects.forms import SiteExplorationForm
from offgridplanner.projects.helpers import format_exploration_sites_data
from offgridplanner.projects.helpers import from_nested_dict
from offgridplanner.projects.helpers import load_project_from_dict
from offgridplanner.projects.helpers import prepare_data_for_export
from offgridplanner.projects.models import Options
from offgridplanner.projects.models import Project
from offgridplanner.projects.models import SiteExploration
from offgridplanner.steps.models import CustomDemand
from offgridplanner.steps.models import EnergySystemDesign
from offgridplanner.steps.models import GridDesign
from offgridplanner.users.models import User


@require_http_methods(["GET"])
def home(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse("projects:projects_list"))
    return render(request, "pages/landing_page.html")


@login_required
@require_http_methods(["GET"])
def projects_list(request, status="analyzing"):
    projects = (
        Project.objects.filter(Q(user=request.user, status=status))
        .distinct()
        .order_by("date_created")
        .select_related("simulation")
        .reverse()
    )
    return render(
        request, "pages/user_projects.html", {"projects": projects, "status": status}
    )


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


@require_http_methods(["GET"])
def export_project_results(request, proj_id):
    # TODO fix formatting and add units
    project = Project.objects.get(id=proj_id)
    # TODO get this data over get_project_data instead
    input_df = pd.Series(model_to_dict(project))
    results_df = pd.Series(model_to_dict(project.simulation.results))
    energy_system_design_df = pd.Series(model_to_dict(project.energysystemdesign))
    energy_flow_df = project.energyflow.df
    nodes_df = project.nodes.df
    links_df = project.links.df
    dataframes = {
        "results": results_df,
        "energy flow": energy_flow_df,
        "user specified input parameters": input_df,
        "nodes": nodes_df,
        "links": links_df,
        "energy system design": energy_system_design_df,
    }

    prepared_data = prepare_data_for_export(dataframes)

    excel_file = io.BytesIO()
    with pd.ExcelWriter(excel_file, engine="xlsxwriter") as writer:
        workbook = writer.book
        # format_right = workbook.add_format({"align": "right"})
        # format_left = workbook.add_format({"align": "left"})

        for sheet_name, df in zip(dataframes.keys(), prepared_data, strict=False):
            df.astype(str).to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            # set_column_width(worksheet, df, format_right if sheet_name != "results" else format_left)

    excel_file.seek(0)

    response = StreamingHttpResponse(
        excel_file,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.headers["Content-Disposition"] = (
        "attachment; filename=offgridplanner_results.xlsx"
    )
    return response


@require_http_methods(["POST"])
def update_project_status(request):
    data = json.loads(request.body)
    project_id = int(data.get("proj_id"))
    new_status = data.get("status")
    project = Project.objects.get(id=project_id)
    project.status = new_status
    project.save()
    return JsonResponse({"success": True})


def export_project_report(proj_id):
    pass


# TODO unused as of now
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
        "EnergySystemDesign": EnergySystemDesign.objects.filter(project=project),
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
        msg = (
            f"The project does not contain all data required for the optimization."
            f" The following models are missing: {missing_qs}"
        )
        raise ValueError(
            msg,
        )
    proj_data = {key: qs.get() for key, qs in model_qs.items()}
    return proj_data


@require_http_methods(["GET", "POST"])
def potential_map(request):
    user = request.user
    site_exploration, _ = SiteExploration.objects.get_or_create(user=user)
    form = SiteExplorationForm(instance=site_exploration)

    # Save the existing MG data in the session storage to avoid sending an API request every time
    if "existing_mgs" in request.session:
        existing_mgs = request.session["existing_mgs"]
    else:
        try:
            existing_mgs = fetch_existing_minigrids()
            request.session["existing_mgs"] = existing_mgs
        except RuntimeError:
            existing_mgs = []

    context = {
        "form": form,
        "existing_mgs": json.dumps(existing_mgs),
        "table_data": [],
        "map_data": [],
    }

    if existing_mgs:
        geojson_initial, _ = format_exploration_sites_data(existing_mgs)
        potential_sites = site_exploration.latest_exploration_results["minigrids"]
        if potential_sites:
            geojson_potential, table_potential = format_exploration_sites_data(
                potential_sites
            )

            context["table_data"] = json.dumps(table_potential)
            context["map_data"] = json.dumps(geojson_potential)

    return render(request, "pages/map.html", context=context)


def start_exploration(request):
    """
    Filter the locations based on the given filters and return both the table html and the geoJSON to populate the map
    """
    data = {}
    site_exploration = request.user.siteexploration
    form = SiteExplorationForm(request.POST, instance=site_exploration)
    if form.is_valid():
        exploration_id = start_site_exploration(json.dumps(form.cleaned_data))
        print(f"Exploration ID: {exploration_id}")
        site_exploration.exploration_id = exploration_id
        site_exploration.save()
        data["status"] = "RUNNING"

    return JsonResponse(data)


def stop_exploration(request):
    site_exploration = request.user.siteexploration
    exploration_id = site_exploration.exploration_id
    res = stop_site_exploration(exploration_id)
    # Don't delete the exploration id, since we actually need it to fetch the results for a specific project
    # site_exploration.exploration_id = None
    # site_exploration.save()
    return JsonResponse(res)


def load_exploration_sites(request):
    site_exploration = request.user.siteexploration
    exploration_id = site_exploration.exploration_id
    res = fetch_exploration_progress(exploration_id)
    # Save the results for loading later
    site_exploration.latest_exploration_results = res
    site_exploration.save()
    status = res["status"]
    data = {"status": status}
    if res["minigrids"]:
        sites = res["minigrids"]
        data["geojson"], data["table"] = format_exploration_sites_data(sites)

    return JsonResponse(data)


def populate_site_data(request):
    site_exploration = request.user.siteexploration
    exploration_id = site_exploration.exploration_id
    site_id = json.loads(request.body).get("site_id")
    res = fetch_potential_minigrid_data(exploration_id, site_id)

    try:
        # Extract the project data and create a new project
        project_input = {"user": request.user, "name": res["id"]} | json.loads(
            res["project_input"]
        )
        # TODO find out where the tax parameter might be needed
        project_input.pop("tax")
        proj, _ = Project.objects.get_or_create(**project_input)

        # Save the nodes and links data
        nodes_data = json.loads(res["grid_results"])["nodes"]
        links_data = json.loads(res["grid_results"])["links"]

        nodes, _ = Nodes.objects.get_or_create(project=proj)
        links, _ = Links.objects.get_or_create(project=proj)
        # Format data to be in the same format as db (# TODO change db format to orient="list" eventually)
        nodes.data = pd.DataFrame(nodes_data).to_json(orient="records")
        nodes.save()
        links.data = pd.DataFrame(links_data).to_json(orient="records")
        links.save()

        # Save the energy system model data
        energy_system_data = json.loads(res["supply_input"])["energy_system_design"]
        energy_system_data = from_nested_dict(EnergySystemDesign, energy_system_data)
        energy_system_design_input = {"project": proj} | energy_system_data
        energy_system, _ = EnergySystemDesign.objects.get_or_create(
            **energy_system_design_input
        )
        energy_system.save()

    except RuntimeError:
        return JsonResponse(
            {"error": "Something went wrong fetching the site data"}, status=400
        )

    return JsonResponse(
        {"redirect_url": reverse("steps:project_setup", args=[proj.id])}
    )
