import os

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms import model_to_dict
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from config.settings.base import DEFAULT_COUNTRY
from config.settings.base import PENDING
from offgridplanner.optimization.models import Results
from offgridplanner.optimization.helpers import get_country_bounds
from offgridplanner.optimization.models import Simulation
from offgridplanner.optimization.supply.demand_estimation import ENTERPRISE_LIST
from offgridplanner.optimization.supply.demand_estimation import LARGE_LOAD_KW_MAPPING
from offgridplanner.optimization.supply.demand_estimation import LARGE_LOAD_LIST
from offgridplanner.optimization.supply.demand_estimation import PUBLIC_SERVICE_LIST
from offgridplanner.projects.forms import OptionForm
from offgridplanner.projects.forms import ProjectForm
from offgridplanner.projects.helpers import OUTPUT_KPIS
from offgridplanner.projects.helpers import get_param_from_metadata
from offgridplanner.projects.helpers import group_form_by_component
from offgridplanner.projects.helpers import reorder_dict
from offgridplanner.projects.models import Project
from offgridplanner.steps.decorators import user_owns_project
from offgridplanner.steps.forms import CustomDemandForm
from offgridplanner.steps.forms import EnergySystemDesignForm
from offgridplanner.steps.forms import GridDesignForm
from offgridplanner.steps.models import CustomDemand
from offgridplanner.steps.models import EnergySystemDesign
from offgridplanner.steps.models import GridDesign
from offgridplanner.users.models import User

STEPS = {
    "project_setup": _("Project Setup"),
    "consumer_selection": _("Consumer Selection"),
    "demand_estimation": _("Demand Estimation"),
    "grid_design": _("Grid Design"),
    "energy_system_design": _("Energy System Design"),
    "simulation_results": _("Simulation Results"),
}

# Remove the calculating step from the top ribbon
STEP_LIST_RIBBON = list(STEPS.values())


@login_required
@user_owns_project
@require_http_methods(["GET", "POST"])
def project_setup(request, proj_id=None):
    project = get_object_or_404(Project, id=proj_id) if proj_id is not None else None
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
            simulation, _ = Simulation.objects.get_or_create(project=project)

        return HttpResponseRedirect(
            reverse("steps:consumer_selection", args=[project.id]),
        )


@login_required
@user_owns_project
@require_http_methods(["GET"])
def consumer_selection(request, proj_id=None):
    if proj_id is None:
        err = "Project ID missing"
        raise ValueError(err)
    else:
        project = get_object_or_404(Project, id=proj_id)

        public_service_list = {
            f"group{ix}": service
            for ix, service in enumerate(sorted(PUBLIC_SERVICE_LIST), 1)
        }
        enterprise_list = {
            f"group{ix}": enterprise
            for ix, enterprise in enumerate(sorted(ENTERPRISE_LIST), 1)
        }
        large_load_list = {
            f"group{ix}": f"{machine} ({LARGE_LOAD_KW_MAPPING[machine]}kW)"
            for ix, machine in enumerate(sorted(LARGE_LOAD_LIST), 1)
        }

        country_bounds = get_country_bounds(proj_id)

        country = project.country
        if country != DEFAULT_COUNTRY[0]:
            timeseries_warning = (
                f"You have not selected {DEFAULT_COUNTRY[1]} as a location. You may continue the "
                f"process, but please consider that the demand assigned to the consumers is based on data specific "
                f"to {DEFAULT_COUNTRY[1]}, and may not accurately reflect electricity demand for other locations."
            )
            messages.add_message(request, messages.WARNING, timeseries_warning)

        context = {
            "public_service_list": public_service_list,
            "enterprise_list": enterprise_list,
            "large_load_list": large_load_list,
            "bounds_dict": country_bounds,
            "step_id": list(STEPS.keys()).index("consumer_selection") + 1,
            "step_list": STEP_LIST_RIBBON,
            "proj_id": proj_id,
        }

        # _wizard.js contains info for the POST function set when clicking on next or on another step

        return render(request, "pages/consumer_selection.html", context)


@login_required
@user_owns_project
@require_http_methods(["GET", "POST"])
def demand_estimation(request, proj_id=None):
    # TODO demand import and export from this step still needs to be handled
    step_id = list(STEPS.keys()).index("demand_estimation") + 1
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)

        custom_demand, _ = CustomDemand.objects.get_or_create(
            project=project, defaults=get_param_from_metadata("default", "CustomDemand")
        )
        if request.method == "GET":
            form = CustomDemandForm(instance=custom_demand)
            calibration_initial = custom_demand.calibration_option
            calibration_active = custom_demand.calibration_option is not None
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


@login_required
@user_owns_project
@require_http_methods(["GET", "POST"])
def grid_design(request, proj_id=None):
    step_id = list(STEPS.keys()).index("grid_design") + 1
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)

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


@login_required
@user_owns_project
@require_http_methods(["GET", "POST"])
def energy_system_design(request, proj_id=None):
    step_id = list(STEPS.keys()).index("energy_system_design") + 1
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)

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


@login_required
@user_owns_project
def calculating(request, proj_id=None):
    # TODO currently the optimization is always triggered through js, add option to reset simulation or skip page if is complete (like open-plan)
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)

        simulation, _ = Simulation.objects.get_or_create(project=project)
        if "anonymous" in project.user.email:
            msg = "You will be forwarded after the model calculation is completed."
            email_opt = False
        else:
            msg = "You will be forwarded after the model calculation is completed."
            email_opt = False
        # TODO there was also the condition len(project.task_id) > 20 but I'm not sure why it is needed
        for opt_type in ["grid", "supply"]:
            token = getattr(simulation, f"token_{opt_type}")
            status = getattr(simulation, f"status_{opt_type}")
            # TODO fix abort now that there are two task ids
            if token != "" and status == PENDING:
                msg = (
                    "CAUTION: You have a calculation in progress that has not yet been completed. Therefore you cannot"
                    " start another calculation. You can cancel the already running calculation by clicking on the"
                    " following button:"
                )

        context = {
            "proj_id": proj_id,
            "msg": msg,
            "time": 3,
            "email_opt": email_opt,
        }
        return render(request, "pages/calculating.html", context)


@login_required
@require_http_methods(["GET"])
def simulation_results(request, proj_id=None):
    step_id = list(STEPS.keys()).index("simulation_results") + 1

    project = get_object_or_404(Project, id=proj_id)
    opts = project.options
    res_qs = Results.objects.filter(simulation=project.simulation)

    if res_qs.exists():
        res = res_qs.get()
    else:
        return redirect("steps:calculating", proj_id)

    df = pd.Series(model_to_dict(res))

    df = df.astype(float)
    output_kpis = OUTPUT_KPIS.copy()

    for kpi in output_kpis:
        output_kpis[kpi]["value"] = df[kpi].round(1)

    country_bounds = get_country_bounds(proj_id)

    nodes_df = project.nodes.df
    min_latitude, min_longitude, max_latitude, max_longitude = (
        nodes_df["latitude"].min(),
        nodes_df["longitude"].min(),
        nodes_df["latitude"].max(),
        nodes_df["longitude"].max(),
    )

    # Currently the explorer returns projects
    # new_mg_data = {
    #     "id": str(project.uuid),
    #     "status": "potential",
    #     "name": project.name,
    #     "operator": "string",
    #     "pv_capacity": output_kpis["pv_capacity"]["value"],
    #     "pv_estimated": True,
    #     "distance_to_grid": 0,
    #     "distance_to_road": 0,
    #     "centroid": {
    #         "bbox": [min_latitude, min_longitude, max_latitude, max_longitude],
    #         "type": "Point",
    #         "coordinates": [
    #             np.average([min_latitude, max_latitude]),
    #             np.average([min_longitude, max_latitude]),
    #         ],
    #     },
    # }

    # TODO re-enable this when no error is thrown
    # notify_existing_minigrids(new_mg_data)
    return render(
        request,
        "pages/simulation_results.html",
        context={
            "proj_id": proj_id,
            "step_id": step_id,
            "results": output_kpis,
            "do_grid_optimization": opts.do_grid_optimization,
            "do_supply_optimization": opts.do_es_design_optimization,
            "bounds_dict": country_bounds,
            "step_list": STEP_LIST_RIBBON,
        },
    )


@login_required
@user_owns_project
@require_http_methods(["GET", "POST"])
def steps(request, proj_id, step_id=None):
    if step_id is None:
        return HttpResponseRedirect(reverse("steps:ogp_steps", args=[proj_id, 1]))

    return HttpResponseRedirect(
        reverse(f"steps:{list(STEPS.keys())[step_id - 1]}", args=[proj_id])
    )


@require_http_methods(["GET"])
def load_previous_data(request, page_name=None, proj_id=None):
    if proj_id is not None:
        project = get_object_or_404(Project, id=proj_id)
        if project.user.email != request.user.email:
            raise PermissionDenied
        # user = await handle_user_accounts.get_user_from_cookie(request)
        # if user is None:
        #     return
        # project_id = request.query_params.get('project_id')
        if page_name == "project_setup":
            pass
        #     if project_id == 'new':
        #         project_id = await async_queries.next_project_id_of_user(user.id)
        #         return sa_tables.ProjectSetup(project_id=project_id)
        #     try:
        #         project_id = int(project_id)
        #     except (ValueError, TypeError):
        #         return None
        #     project_setup = await async_queries.get_model_instance(sa_tables.ProjectSetup, user.id, project_id)
        #     if hasattr(project_setup, 'start_date'):
        #         project_setup.start_datetime = project_setup.start_date.date().__str__()
        #         return project_setup
        #     else:
        #         return None
        elif page_name == "grid_design":
            grid_design = GridDesign.get(project=project)
            return grid_design
        # elif page_name == "demand_estimation":
        # try:
        #     project_id = int(project_id)
        # except (ValueError, TypeError):
        #     return None
        # demand_estimation = await async_queries.get_model_instance(sa_tables.Demand, user.id, project_id)
        # if (demand_estimation is not None
        #         and hasattr(demand_estimation, 'use_custom_demand')
        #         and demand_estimation.use_custom_demand is True):
        #     return demand_estimation
        # if demand_estimation is None or not hasattr(demand_estimation, 'maximum_peak_load'):
        #     return None
        # if pd.Series([value for key, value in demand_estimation.to_dict().items() if 'custom_share_' in key]).fillna(0).sum() == 0:
        #     wealth_share_dict = default_wealth_share()
        #     demand_estimation.custom_share_1 = wealth_share_dict['custom_share_1']
        #     demand_estimation.custom_share_2 = wealth_share_dict['custom_share_2']
        #     demand_estimation.custom_share_3 = wealth_share_dict['custom_share_3']
        #     demand_estimation.custom_share_4 = wealth_share_dict['custom_share_4']
        #     demand_estimation.custom_share_5 = wealth_share_dict['custom_share_5']
        # demand_estimation.maximum_peak_load = str(demand_estimation.maximum_peak_load) \
        #     if demand_estimation.maximum_peak_load is not None else ''
        # demand_estimation.average_daily_energy = str(demand_estimation.average_daily_energy) \
        #     if demand_estimation.average_daily_energy is not None else ''
        # demand_estimation.custom_calibration = True \
        #     if len(demand_estimation.maximum_peak_load) > 0 or len(demand_estimation.average_daily_energy) > 0 \
        #     else False
        # demand_estimation.calibration_options = 2 if len(demand_estimation.maximum_peak_load) > 0 else 1
        # return demand_estimation
        elif page_name == "energy_system_design":
            energy_system_design = EnergySystemDesign.objects.get(project=project)
            return energy_system_design
