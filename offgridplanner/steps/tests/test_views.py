import json
from http import HTTPStatus
from pathlib import Path

import pytest
from django.urls import reverse

from config.settings.base import EXAMPLE_PROJECT_PATH
from offgridplanner.projects.models import Project
from offgridplanner.projects.views import populate_project_from_export
from offgridplanner.users.tests.factories import UserFactory


@pytest.fixture
def project(db):
    user = UserFactory()
    with Path(EXAMPLE_PROJECT_PATH).open() as f:
        data = json.load(f)
    proj_id = populate_project_from_export(data, user)
    return Project.objects.get(id=proj_id)


@pytest.fixture
def auth_client(client, project):
    client.force_login(project.user)
    return client


@pytest.mark.django_db
class TestStepViewsReturn200:
    def test_project_setup_get(self, auth_client, project):
        response = auth_client.get(reverse("steps:project_setup", args=[project.id]))
        assert response.status_code == HTTPStatus.OK

    def test_consumer_selection_get(self, auth_client, project):
        response = auth_client.get(
            reverse("steps:consumer_selection", args=[project.id])
        )
        assert response.status_code == HTTPStatus.OK

    def test_demand_estimation_get(self, auth_client, project):
        response = auth_client.get(
            reverse("steps:demand_estimation", args=[project.id])
        )
        assert response.status_code == HTTPStatus.OK

    def test_grid_design_get(self, auth_client, project):
        response = auth_client.get(reverse("steps:grid_design", args=[project.id]))
        assert response.status_code == HTTPStatus.OK

    def test_energy_system_design_get(self, auth_client, project):
        response = auth_client.get(
            reverse("steps:energy_system_design", args=[project.id])
        )
        assert response.status_code == HTTPStatus.OK

    def test_calculating_get(self, auth_client, project):
        response = auth_client.get(reverse("steps:calculating", args=[project.id]))
        assert response.status_code == HTTPStatus.OK

    def test_simulation_results_redirects_when_no_results(self, auth_client, project):
        # No Results exist yet → redirects to calculating
        response = auth_client.get(
            reverse("steps:simulation_results", args=[project.id])
        )
        assert response.status_code == HTTPStatus.FOUND


@pytest.mark.django_db
class TestStepViewsAuthentication:
    def test_unauthenticated_redirects_to_login(self, client, project):
        response = client.get(reverse("steps:project_setup", args=[project.id]))
        assert response.status_code == HTTPStatus.FOUND
        assert "login" in response.url or "signin" in response.url

    def test_other_user_redirects_to_projects_list(self, client, project):
        other = UserFactory()
        client.force_login(other)
        response = client.get(reverse("steps:project_setup", args=[project.id]))
        assert response.status_code == HTTPStatus.FOUND
