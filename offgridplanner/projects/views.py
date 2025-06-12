import io
import json
import os

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
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from offgridplanner.optimization.models import Nodes
from offgridplanner.projects.helpers import load_project_from_dict
from offgridplanner.projects.helpers import prepare_data_for_export
from offgridplanner.projects.models import MapTestSite
from offgridplanner.projects.models import Options
from offgridplanner.projects.models import Project
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


def potential_map(request):
    return render(request, "pages/map.html")



def filter_locations(request):
    """
    Filter the locations based on the given filters and return both the table html and the geoJSON to populate the map
    """
    reset = request.POST.get("reset")
    data = {}
    if reset:
        sites = MapTestSite.objects.all()
    else:
        site_filter = {}
        for param, dtype in zip(
            ["min_building_count", "diameter_max", "min_grid_dist"],
            [int, int, float],
            strict=False,
        ):
            val = request.POST.get(param) if request.POST.get(param) != "" else 0
            site_filter[param] = dtype(val)

        sites = MapTestSite.objects.filter(
            building_count__gte=site_filter["min_building_count"],
            diameter_max__lte=site_filter["diameter_max"],
            grid_dist__gte=site_filter["min_grid_dist"],
        )

    # generate table HTML
    context = {"sites": sites}
    data["table"] = render_to_string("widgets/table_template.html", context, request)

    # generate geoJSON for map
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [site.longitude, site.latitude],
            },
            "properties": {
                "name": site.id,
                "building_count": site.building_count,
                "grid_dist": site.grid_dist,
            },
        }
        for site in sites
    ]
    data["geojson"] = features

    return JsonResponse(data)
