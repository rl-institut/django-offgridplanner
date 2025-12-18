import contextlib

from offgridplanner.steps.models import Project


def current_project(request):
    """
    Add the current project name to all templates, if available.
    """
    project = None
    rm = request.resolver_match
    if rm and rm.kwargs:
        project_id = rm.kwargs.get("proj_id")
        if project_id:
            # pass if the project does not exist (may be the case for step 1, before it is saved to the database)
            with contextlib.suppress(Project.DoesNotExist):
                project = Project.objects.get(pk=project_id)

    return {"project": project}
