import json
from pathlib import Path

import pytest

from config.settings.base import EXAMPLE_PROJECT_PATH
from offgridplanner.projects.models import Project
from offgridplanner.projects.views import populate_project_from_export
from offgridplanner.users.tests.factories import UserFactory


@pytest.fixture
def example_project_data():
    with Path(EXAMPLE_PROJECT_PATH).open() as f:
        return json.load(f)


@pytest.fixture
def project(db, example_project_data):
    user = UserFactory()
    proj_id = populate_project_from_export(example_project_data, user)
    return Project.objects.get(id=proj_id)


@pytest.mark.django_db
class TestProjectExport:
    def test_export_has_proj_key(self, project):
        result = project.export()
        assert "proj" in result

    def test_proj_excludes_id_user_options(self, project):
        proj_dict = project.export()["proj"]
        assert "id" not in proj_dict
        assert "user" not in proj_dict
        assert "options" not in proj_dict

    def test_proj_includes_core_fields(self, project):
        proj_dict = project.export()["proj"]
        for field in ["name", "interest_rate", "lifetime", "n_days", "country"]:
            assert field in proj_dict

    def test_export_includes_nodes(self, project):
        assert "nodes" in project.export()

    def test_export_includes_grid_design(self, project):
        assert "grid_design" in project.export()

    def test_export_includes_custom_demand(self, project):
        assert "custom_demand" in project.export()

    def test_export_grid_design_is_json_string(self, project):
        result = project.export()
        assert isinstance(result["grid_design"], str)
        assert isinstance(json.loads(result["grid_design"]), dict)

    def test_export_roundtrip_creates_new_project(self, project):
        export = project.export()
        new_id = populate_project_from_export(export, UserFactory())
        assert Project.objects.filter(id=new_id).exists()

    def test_export_roundtrip_preserves_project_name(self, project):
        export = project.export()
        new_id = populate_project_from_export(export, UserFactory())
        assert Project.objects.get(id=new_id).name == project.name
