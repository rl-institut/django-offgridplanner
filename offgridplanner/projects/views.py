# Create your views here.
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


# @login_required
@require_http_methods(["GET"])
def projects_list(request, proj_id=None):
    return render(request, "pages/user_projects.html")
