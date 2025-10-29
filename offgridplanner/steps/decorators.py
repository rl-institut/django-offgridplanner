from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from offgridplanner.projects.models import Project


def user_owns_project(view_func):
    @wraps(view_func)
    def _wrapped_view(request, proj_id=None, *args, **kwargs):
        project = Project.objects.get(id=proj_id) if proj_id else None
        if project:
            if project.user != request.user:
                messages.error(
                    request, "You don't have permission to view this project."
                )
                return redirect("projects:projects_list")
        return view_func(request, proj_id, *args, **kwargs)

    return _wrapped_view
