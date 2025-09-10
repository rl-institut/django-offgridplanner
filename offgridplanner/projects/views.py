import base64
import io
import json
import urllib
from http.client import HTTPException

# from jsonview.decorators import json_view
import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
from openpyxl.drawing.image import PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import Image
from svglib.svglib import svg2rlg

from offgridplanner.optimization.helpers import process_optimization_results
from offgridplanner.optimization.models import Links
from offgridplanner.optimization.models import Nodes
from offgridplanner.optimization.models import Simulation
from offgridplanner.optimization.requests import fetch_existing_minigrids
from offgridplanner.optimization.processing import PreProcessor
from offgridplanner.projects.exports import create_pdf_report
from offgridplanner.projects.exports import prepare_data_for_export
from offgridplanner.projects.exports import project_data_df_to_xlsx
from offgridplanner.projects.helpers import collect_project_dataframes
from offgridplanner.optimization.requests import fetch_exploration_progress
from offgridplanner.optimization.requests import fetch_potential_minigrid_data
from offgridplanner.optimization.requests import start_site_exploration
from offgridplanner.optimization.requests import stop_site_exploration
from offgridplanner.projects.forms import SiteExplorationForm
from offgridplanner.projects.helpers import format_exploration_sites_data
from offgridplanner.projects.helpers import from_nested_dict
from offgridplanner.projects.helpers import load_project_from_dict
from offgridplanner.projects.models import Options
from offgridplanner.projects.models import Project
from offgridplanner.projects.models import SiteExploration
from offgridplanner.steps.decorators import user_owns_project
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


@login_required
@user_owns_project
@require_http_methods(["GET", "POST"])
def project_duplicate(request, proj_id):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        # TODO check user rights to the project
        dm = project.export()
        user = User.objects.get(email=request.user.email)
        # TODO must find user from its email address
        new_proj_id = load_project_from_dict(dm, user=user)

    return HttpResponseRedirect(reverse("projects:projects_list"))


@login_required
@user_owns_project
@require_http_methods(["POST"])
def project_delete(request, proj_id):
    project = get_object_or_404(Project, id=proj_id)

    if request.method == "POST":
        project.delete()
        # message not defined
        messages.success(request, "Project successfully deleted!")

    return HttpResponseRedirect(reverse("projects:projects_list"))


@login_required
@user_owns_project
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
    potential_sites = site_exploration.latest_exploration_results
    if potential_sites:
        geojson_potential, table_potential = format_exploration_sites_data(
            potential_sites["minigrids"]
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
        project_input = {
            "user": request.user,
            "name": res["id"],
            "uuid": res["id"],
        } | json.loads(res["project_input"])
        # TODO find out where the tax parameter might be needed
        project_input.pop("tax")
        proj, _ = Project.objects.get_or_create(**project_input)
        proj.options = Options.objects.create()
        proj.save()

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

        # Save the grid model data
        grid_design_data = json.loads(res["grid_input"])["grid_design"]
        grid_design_data = from_nested_dict(GridDesign, grid_design_data)
        grid_design_input = {"project": proj} | grid_design_data
        grid_design, _ = GridDesign.objects.get_or_create(**grid_design_input)
        grid_design.save()

        # Create a CustomDemand object to save the demand
        # TODO if the consumers are changed the custom demand should be overwritten
        # custom_demand, _ = CustomDemand.objects.get_or_create(project=proj)
        # demand = json.loads(res["supply_input"])["sequences"]["demand"]
        # custom_demand.uploaded_data = pd.DataFrame(demand, columns=["demand"]).to_json()

        # Save the optimization results
        optimization_results = {
            "supply": json.loads(res["supply_results"]),
            "grid": json.loads(res["grid_results"]),
        }

        sim, _ = Simulation.objects.get_or_create(
            project=proj, status_grid="DONE", status_supply="DONE"
        )
        process_optimization_results(proj.id, optimization_results)

    except RuntimeError:
        return JsonResponse(
            {"error": "Something went wrong fetching the site data"}, status=400
        )

    return JsonResponse(
        {"redirect_url": reverse("steps:project_setup", args=[proj.id])}
    )


# TODO refactor function to pass ruff
@login_required
@user_owns_project
@require_http_methods(["POST"])
def download_pdf_report(request, proj_id):  # noqa:PLR0915
    dataframes = collect_project_dataframes(proj_id)
    data = json.loads(request.body)
    images = data.get("images", [])  # TODO check format and set default
    input_parameters_df = dataframes["input_parameters_df"]
    energy_flow_df = dataframes["energy_flow_df"]
    if not images or not isinstance(images, list):
        raise HTTPException(status_code=400, detail="No images data provided")
    image_dict = {}
    for image in images:
        plot_id = image.get("id")
        image_data = image.get("data")
        if not plot_id or not image_data:
            continue
        if plot_id == "map" and not input_parameters_df["do_grid_optimization"].iloc[0]:
            continue
        if not input_parameters_df["do_es_design_optimization"].iloc[0]:
            if plot_id in [
                "optimalSizes",
                "sankeyDiagram",
                "energyFlows",
                "lcoeBreakdown",
                "demandCoverage",
            ]:
                continue
        if image_data.startswith("data:image/svg+xml,"):
            left_margin = 2.4 * inch  # Example value
            right_margin = 1 * inch  # Example value
            image_data = image_data.replace("data:image/svg+xml,", "")
            svg_text = urllib.parse.unquote(image_data)
            img_bytes = svg_text.encode("utf-8")
            drawing = svg2rlg(io.BytesIO(img_bytes))
            drawing_width = drawing.width
            drawing_height = drawing.height
            max_width, max_height = A4
            max_width -= 1 * inch
            max_height -= 1 * inch
            scale_x = max_width / drawing_width
            scale_y = max_height / drawing_height
            scale = min(scale_x, scale_y, 1)
            drawing.scale(scale, scale)
            delta_margin = left_margin - right_margin
            shift_x = -delta_margin / 2  # Negative to shift left
            drawing.translate(shift_x, 0)
            image_dict[plot_id] = drawing
        else:
            img_bytes = image_data.replace("data:image/png;base64,", "")
            img_bytes = base64.b64decode(img_bytes)
            image_io = io.BytesIO(img_bytes)
            pil_image = PILImage.open(image_io)
            width_px, height_px = pil_image.size
            dpi = 96
            width_inch = width_px / dpi
            height_inch = height_px / dpi
            image_io.seek(0)
            max_width, max_height = A4
            max_width = max_width / inch - 1
            max_height = max_height / inch - 1
            scale_x = min(max_width / width_inch, 1)
            scale_y = min(max_height / height_inch, 1)
            scale = min(scale_x, scale_y)
            final_width = width_inch * scale * inch
            final_height = height_inch * scale * inch
            img = Image(image_io, width=final_width, height=final_height)
            image_dict[plot_id] = img
    if "demand" not in energy_flow_df.columns:
        energy_flow_df["demand"] = PreProcessor(proj_id).demand
    doc, buffer = create_pdf_report(image_dict, dataframes)

    buffer.seek(0)  # ensure we're at the start
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        'attachment; filename="offgridplanner_results.pdf"'
    )
    return response


@login_required
@user_owns_project
@require_http_methods(["GET"])
def download_excel_results(request, proj_id):
    dataframes = collect_project_dataframes(proj_id)
    input_parameters_df = dataframes["input_parameters_df"]
    energy_flow_df = dataframes["energy_flow_df"]
    energy_system_design = dataframes["energy_system_design_df"]
    results_df = dataframes["results_df"]
    nodes_df = dataframes["nodes_df"]
    links_df = dataframes["links_df"]

    excel_file = project_data_df_to_xlsx(
        input_parameters_df,
        energy_system_design,
        energy_flow_df,
        results_df,
        nodes_df,
        links_df,
    )
    return HttpResponse(
        excel_file,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="offgridplanner_results.xlsx"'
        },
    )
