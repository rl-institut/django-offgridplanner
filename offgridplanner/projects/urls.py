from django.urls import path

from .views import *

app_name = "projects"

urlpatterns = [
    path("projects_list", projects_list, name="projects_list"),
]
