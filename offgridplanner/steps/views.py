from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def home(request):
    return render(
        request,
        "pages/landing_page.html",
        {"step_list": STEPS.keys()},
    )


# @login_required()
@require_http_methods(["GET"])
def project_setup(request, proj_id=None):
    from offgridplanner.projects.forms import ProjectForm

    form = ProjectForm()
    context = {"form": form}
    if proj_id is not None:
        max_days = int(os.environ.get("MAX_DAYS", 365))
        project = get_object_or_404(Project, id=proj_id)
        if project.user != request.user:
            raise PermissionDenied
        context = {"project_id": project.id, "max_days": max_days}

    # TODO in the js figure out what this is supposed to mean, this make the next button jump to either step 'consumer_selection'
    # or step 'demand_estimation'
    # const consumerSelectionHref = `consumer_selection?project_id=${project_id}`;
    # const demandEstimationHref = `demand_estimation?project_id =${project_id}`;
    # If Consumer Selection is hidden (in raw html), go to demand_estimation

    return render(request, "pages/project_setup.html", context)


# @login_required()
@require_http_methods(["GET"])
def consumer_selection(request):
    return render(request, "pages/consumer_selection.html")


# @login_required()
@require_http_methods(["GET"])
def demand_estimation(request):
    return render(request, "pages/demand_estimation.html")


# @login_required()
@require_http_methods(["GET"])
def grid_design(request):
    return render(request, "pages/grid_design.html")


# @login_required()
@require_http_methods(["GET"])
def energy_system_design(request):
    return render(request, "pages/energy_system_design.html")


# @login_required()
@require_http_methods(["GET"])
def simulation_results(request):
    return render(request, "pages/simulation_results.html")


STEPS = {
    "project_setup": project_setup,
    "consumer_selection": consumer_selection,
    "demand_estimation": demand_estimation,
    "grid_design": grid_design,
    "energy_system_design": energy_system_design,
    "simulation_results": simulation_results,
}


# @login_required
@require_http_methods(["GET", "POST"])
def steps(request, proj_id, step_id=None):
    if step_id is None:
        return HttpResponseRedirect(reverse("steps", args=[proj_id, 1]))

    return STEPS[step_id - 1](request, proj_id, step_id)
