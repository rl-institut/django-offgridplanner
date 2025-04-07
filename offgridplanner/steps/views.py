import json
import os
from collections import defaultdict

import pandas as pd
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from offgridplanner.projects.helpers import (
    reorder_dict,
    group_form_by_component,
    get_param_from_metadata,
    FORM_FIELD_METADATA,
)
from offgridplanner.steps.forms import CustomDemandForm, EnergySystemDesignForm
from offgridplanner.steps.forms import GridDesignForm
from offgridplanner.projects.forms import OptionForm
from offgridplanner.projects.forms import ProjectForm
from offgridplanner.steps.models import CustomDemand
from offgridplanner.steps.models import EnergySystemDesign
from offgridplanner.steps.models import GridDesign
from offgridplanner.projects.models import Project
from offgridplanner.optimization.models import Simulation
from offgridplanner.optimization.tasks import task_is_finished
from offgridplanner.users.models import User

STEPS = {
    "project_setup": _("Project Setup"),
    "consumer_selection": _("Consumer Selection"),
    "demand_estimation": _("Demand Estimation"),
    "grid_design": _("Grid Design"),
    "energy_system_design": _("Energy System Design"),
    "calculating": _("Calculating"),
    "simulation_results": _("Simulation Results"),
}

# Remove the calculating step from the top ribbon
STEP_LIST_RIBBON = [step for step in STEPS.values() if step != _("Calculating")]


# @login_required()
@require_http_methods(["GET", "POST"])
def project_setup(request, proj_id=None):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied
    else:
        project = None
    if request.method == "GET":
        max_days = int(os.environ.get("MAX_DAYS", 365))

        context = {}
        if project is not None:
            form = ProjectForm(instance=project)
            opts = OptionForm(instance=project.options)
            context.update({"proj_id": project.id})
        else:
            form = ProjectForm(initial=get_param_from_metadata("default", "Project"))
            opts = OptionForm()
        context.update(
            {
                "form": form,
                "opts_form": opts,
                # fields that should be rendered in left column (for use in template tags)
                "left_col_fields": ["name", "n_days", "description"],
                "max_days": max_days,
                "step_id": list(STEPS.keys()).index("project_setup") + 1,
                "step_list": STEP_LIST_RIBBON,
            },
        )

        # TODO in the js figure out what this is supposed to mean, this make the next button jump to either step 'consumer_selection'
        # or step 'demand_estimation'
        # const consumerSelectionHref = `consumer_selection?project_id=${project_id}`;
        # const demandEstimationHref = `demand_estimation?project_id =${project_id}`;
        # If Consumer Selection is hidden (in raw html), go to demand_estimation

        return render(request, "pages/project_setup.html", context)
    if request.method == "POST":
        if project is None:
            form = ProjectForm(request.POST)
            opts_form = OptionForm(request.POST)
        else:
            form = ProjectForm(request.POST, instance=project)
            opts_form = OptionForm(request.POST, instance=project.options)
        if form.is_valid() and opts_form.is_valid():
            opts = opts_form.save()
            if project is None:
                project = form.save(commit=False)
                project.user = User.objects.get(email=request.user.email)
                project.options = opts
            project.save()

        return HttpResponseRedirect(
            reverse("steps:consumer_selection", args=[project.id]),
        )


# @login_required()
@require_http_methods(["GET"])
def consumer_selection(request, proj_id=None):
    # TODO replace these with lists from LOAD_PROFILES.columns
    public_service_list = {
        "group1": "Health_Health Centre",
        "group2": "Health_Clinic",
        "group3": "Health_CHPS",
        "group4": "Education_School",
        "group5": "Education_School_noICT",
    }

    enterprise_list = {
        "group1": "Food_Groceries",
        "group2": "Food_Restaurant",
        "group3": "Food_Bar",
        "group4": "Food_Drinks",
        "group5": "Food_Fruits or vegetables",
        "group6": "Trades_Tailoring",
        "group7": "Trades_Beauty or Hair",
        "group8": "Trades_Metalworks",
        "group9": "Trades_Car or Motorbike Repair",
        "group10": "Trades_Carpentry",
        "group11": "Trades_Laundry",
        "group12": "Trades_Cycle Repair",
        "group13": "Trades_Shoemaking",
        "group14": "Retail_Medical",
        "group15": "Retail_Clothes and accessories",
        "group16": "Retail_Electronics",
        "group17": "Retail_Other",
        "group18": "Retail_Agricultural",
        "group19": "Digital_Mobile or Electronics Repair",
        "group20": "Digital_Digital Other",
        "group21": "Digital_Cybercafé",
        "group22": "Digital_Cinema or Betting",
        "group23": "Digital_Photostudio",
        "group24": "Agricultural_Mill or Thresher or Grater",
        "group25": "Agricultural_Other",
    }

    enterpise_option = ""

    large_load_list = {
        "group1": "Milling Machine (7.5kW)",
        "group2": "Crop Dryer (8kW)",
        "group3": "Thresher (8kW)",
        "group4": "Grinder (5.2kW)",
        "group5": "Sawmill (2.25kW)",
        "group6": "Circular Wood Saw (1.5kW)",
        "group7": "Jigsaw (0.4kW)",
        "group8": "Drill (0.4kW)",
        "group9": "Welder (5.25kW)",
        "group10": "Angle Grinder (2kW)",
    }
    large_load_type = "group1"

    option_load = ""

    context = {
        "public_service_list": public_service_list,
        "enterprise_list": enterprise_list,
        "large_load_list": large_load_list,
        "large_load_type": large_load_type,
        "enterpise_option": enterpise_option,
        "option_load": option_load,
        "step_id": list(STEPS.keys()).index("consumer_selection") + 1,
        "step_list": STEP_LIST_RIBBON,
    }
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user.email != request.user.email:
            raise PermissionDenied
        context["proj_id"] = project.id

    # _wizard.js contains info for the POST function set when clicking on next or on another step

    return render(request, "pages/consumer_selection.html", context)


# @login_required()
@require_http_methods(["GET", "POST"])
def demand_estimation(request, proj_id=None):
    # TODO demand import and export from this step still needs to be handled
    step_id = list(STEPS.keys()).index("demand_estimation") + 1
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied

        custom_demand, _ = CustomDemand.objects.get_or_create(
            project=project, defaults=get_param_from_metadata("default", "CustomDemand")
        )
        if request.method == "GET":
            form = CustomDemandForm(instance=custom_demand)
            calibration_initial = custom_demand.calibration_option
            calibration_active = (
                True if custom_demand.calibration_option is not None else False
            )
            context = {
                "calibration": {
                    "active": calibration_active,
                    "initial": calibration_initial,
                },
                "form": form,
                "proj_id": proj_id,
                "step_id": step_id,
                "step_list": STEP_LIST_RIBBON,
            }

            return render(request, "pages/demand_estimation.html", context)

        if request.method == "POST":
            form = CustomDemandForm(request.POST, instance=custom_demand)
            if form.is_valid():
                form.save()

            return redirect("steps:ogp_steps", proj_id, step_id + 1)


# @login_required()
@require_http_methods(["GET", "POST"])
def grid_design(request, proj_id=None):
    step_id = list(STEPS.keys()).index("grid_design") + 1
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied

        grid_design, _ = GridDesign.objects.get_or_create(
            project=project, defaults=get_param_from_metadata("default", "GridDesign")
        )
        if request.method == "GET":
            form = GridDesignForm(instance=grid_design, set_db_column_attribute=True)
            # Group form fields by component (for easier rendering inside boxes)
            grouped_fields = group_form_by_component(form)

            for component in list(grouped_fields):
                clean_name = (
                    component.title().replace("_", " ")
                    if component != "mg"
                    else "Connection Costs"
                )
                grouped_fields[clean_name] = grouped_fields.pop(component)

            # Reorder dictionary for easier rendering in the correct order in the template (move SHS fields to #3)
            grouped_fields = reorder_dict(grouped_fields, 4, 2)

            context = {
                "grouped_fields": grouped_fields,
                "proj_id": proj_id,
                "step_id": step_id,
                "step_list": STEP_LIST_RIBBON,
            }
            return render(request, "pages/grid_design.html", context)

        if request.method == "POST":
            form = GridDesignForm(request.POST, instance=grid_design)
            if form.is_valid():
                form.save()

            return redirect("steps:ogp_steps", proj_id, step_id + 1)


# @login_required()
@require_http_methods(["GET", "POST"])
def energy_system_design(request, proj_id=None):
    step_id = list(STEPS.keys()).index("energy_system_design") + 1
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user.email != request.user.email:
            raise PermissionDenied

    energy_system_design, _ = EnergySystemDesign.objects.get_or_create(
        project=project,
        defaults=get_param_from_metadata("default", "EnergySystemDesign"),
    )
    if request.method == "GET":
        form = EnergySystemDesignForm(
            instance=energy_system_design,
            set_db_column_attribute=True,
        )

        grouped_fields = group_form_by_component(form)

        for component in list(grouped_fields):
            clean_name = component.title().replace("_", " ")
            grouped_fields[clean_name] = grouped_fields.pop(component)

        grouped_fields.default_factory = None

        context = {
            "proj_id": project.id,
            "step_id": step_id,
            "step_list": STEP_LIST_RIBBON,
            "grouped_fields": grouped_fields,
        }

        # TODO read js/pages/energy-system-design.js
        # todo restore using load_previous_data in the first place, then replace with Django forms

        return render(request, "pages/energy_system_design.html", context)
    if request.method == "POST":
        form = EnergySystemDesignForm(
            request.POST, instance=energy_system_design, set_db_column_attribute=True
        )
        if form.is_valid():
            form.save()
        return redirect("steps:ogp_steps", proj_id, step_id + 1)


def calculating(request, proj_id=None):
    # TODO currently the optimization is always triggered through js, add option to reset simulation or skip page if is complete (like open-plan)
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user.email != request.user.email:
            raise PermissionDenied

        simulation, _ = Simulation.objects.get_or_create(project=project)
        if "anonymous" in project.user.email:
            msg = "You will be forwarded after the model calculation is completed."
            email_opt = False
        else:
            msg = (
                "You will be forwarded after the model calculation is completed. You can also close the window and view"
                " the results in your user account after the calculation is finished."
            )
            email_opt = False
        # TODO there was also the condition len(project.task_id) > 20 but I'm not sure why it is needed
        if simulation.task_id is not None and not task_is_finished(simulation.task_id):
            msg = (
                "CAUTION: You have a calculation in progress that has not yet been completed. Therefore you cannot"
                " start another calculation. You can cancel the already running calculation by clicking on the"
                " following button:"
            )

        context = {
            "proj_id": proj_id,
            "msg": msg,
            "task_id": simulation.task_id,
            "time": 3,
            "email_opt": email_opt,
        }
        return render(request, "pages/calculating.html", context)


# @login_required()
@require_http_methods(["GET"])
def simulation_results(request, proj_id=None):
    step_id = list(STEPS.keys()).index("calculating") + 1
    return render(
        request,
        "pages/simulation_results.html",
        context={
            "proj_id": proj_id,
            "step_id": step_id,
            "step_list": STEP_LIST_RIBBON,
        },
    )


# @login_required
@require_http_methods(["GET", "POST"])
def steps(request, proj_id, step_id=None):
    if step_id is None:
        return HttpResponseRedirect(reverse("steps:ogp_steps", args=[proj_id, 1]))

    return HttpResponseRedirect(
        reverse(f"steps:{list(STEPS.keys())[step_id - 1]}", args=[proj_id])
    )
