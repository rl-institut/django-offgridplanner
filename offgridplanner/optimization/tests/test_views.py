import json
from http import HTTPStatus
from pathlib import Path

import pytest
from django.urls import reverse

from config.settings.base import EXAMPLE_PROJECT_PATH
from offgridplanner.optimization.models import Nodes
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


# ---------- db_nodes_to_js ----------


@pytest.mark.django_db
class TestDbNodesToJs:
    def test_returns_200_with_nodes(self, auth_client, project):
        url = reverse("optimization:db_nodes_to_js", args=[project.id])
        assert auth_client.get(url).status_code == HTTPStatus.OK

    def test_response_contains_map_elements_and_is_load_center(
        self, auth_client, project
    ):
        url = reverse("optimization:db_nodes_to_js", args=[project.id])
        data = auth_client.get(url).json()
        assert "map_elements" in data
        assert "is_load_center" in data

    def test_missing_proj_id_returns_400(self, auth_client):
        url = reverse("optimization:db_nodes_to_js")
        assert auth_client.get(url).status_code == HTTPStatus.BAD_REQUEST


# ---------- consumer_to_db ----------


@pytest.mark.django_db(transaction=True)
class TestConsumerToDb:
    @pytest.fixture
    def consumer_row(self):
        return {
            "latitude": 9.0,
            "longitude": 7.0,
            "how_added": "manual",
            "node_type": "consumer",
            "consumer_type": "household",
            "consumer_detail": "default",
            "custom_specification": "",
            "shs_options": 0,
            "is_connected": True,
        }

    def test_saves_nodes_returns_200(self, auth_client, project, consumer_row):
        url = reverse("optimization:consumer_to_db", args=[project.id])
        payload = {"map_elements": [consumer_row], "file_type": "db"}
        response = auth_client.post(
            url, json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == HTTPStatus.OK

    def test_empty_map_elements_deletes_nodes(self, auth_client, project):
        url = reverse("optimization:consumer_to_db", args=[project.id])
        payload = {"map_elements": [], "file_type": "db"}
        auth_client.post(url, json.dumps(payload), content_type="application/json")
        assert not Nodes.objects.filter(project=project).exists()


# ---------- remove_buildings_inside_boundary ----------


@pytest.mark.django_db
class TestRemoveBuildingsInsideBoundary:
    # Note: proj_id is in the URL but unused by the view — no project lookup needed.

    @pytest.fixture
    def boundary_payload(self):
        return {
            "map_elements": [
                {"latitude": 0.5, "longitude": 0.5},  # inside → removed
                {"latitude": 10.0, "longitude": 10.0},  # outside → kept
            ],
            "boundary_coordinates": [
                [
                    [
                        {"lat": 0.0, "lng": 0.0},
                        {"lat": 0.0, "lng": 1.0},
                        {"lat": 1.0, "lng": 1.0},
                        {"lat": 1.0, "lng": 0.0},
                    ]
                ]
            ],
        }

    def test_returns_200(self, client, boundary_payload, project):
        url = reverse(
            "optimization:remove_buildings_inside_boundary", args=[project.id]
        )
        response = client.post(
            url, json.dumps(boundary_payload), content_type="application/json"
        )
        assert response.status_code == HTTPStatus.OK

    def test_removes_elements_inside_boundary(self, client, boundary_payload, project):
        url = reverse(
            "optimization:remove_buildings_inside_boundary", args=[project.id]
        )
        response = client.post(
            url, json.dumps(boundary_payload), content_type="application/json"
        )
        result = response.json()["map_elements"]
        assert len(result) == 1
        assert result[0]["latitude"] == 10.0  # noqa: PLR2004
