import json

from offgridplanner.optimization.models import Nodes


def _nodes_from(rows):
    n = Nodes()
    n.data = json.dumps(rows)
    return n


def _household(label="h1", consumer_detail="default", *, is_connected=True):
    return {
        "label": label,
        "consumer_type": "household",
        "consumer_detail": consumer_detail,
        "is_connected": is_connected,
        "custom_specification": "",
    }


def _enterprise(
    label="e1", consumer_detail="Bakery", machinery="", *, is_connected=True
):
    return {
        "label": label,
        "consumer_type": "enterprise",
        "consumer_detail": consumer_detail,
        "is_connected": is_connected,
        "custom_specification": machinery,
    }


class TestNodes:
    def test_df_uses_label_as_index(self):
        nodes = _nodes_from([_household("h1"), _enterprise("e1")])
        assert nodes.df.index.name == "label"
        assert "h1" in nodes.df.index

    def test_filter_consumers_returns_only_matching_type(self):
        nodes = _nodes_from([_household("h1"), _enterprise("e1")])
        result = nodes.filter_consumers("household")
        assert (result["consumer_type"] == "household").all()
        assert "e1" not in result.index

    def test_filter_consumers_excludes_disconnected(self):
        nodes = _nodes_from(
            [
                _household("h1", is_connected=True),
                _household("h2", is_connected=False),
            ]
        )
        result = nodes.filter_consumers("household")
        assert "h1" in result.index
        assert "h2" not in result.index

    def test_filter_consumers_returns_empty_for_absent_type(self):
        nodes = _nodes_from([_household("h1")])
        assert nodes.filter_consumers("public_service").empty

    def test_counts_groups_by_type_and_detail(self):
        nodes = _nodes_from([_household("h1"), _household("h2"), _enterprise("e1")])
        counts = nodes.counts
        assert counts.loc["household", "default"] == 2  # noqa: PLR2004
        assert counts.loc["enterprise", "Bakery"] == 1

    def test_counts_includes_all_consumer_types(self):
        nodes = _nodes_from([_household("h1"), _enterprise("e1")])
        counts = nodes.counts
        assert "household" in counts.index.get_level_values(0)
        assert "enterprise" in counts.index.get_level_values(0)

    def test_have_custom_machinery_true_when_specification_present(self):
        nodes = _nodes_from([_enterprise("e1", machinery="1 x Welder (5.25kW)")])
        assert nodes.have_custom_machinery is True

    def test_have_custom_machinery_false_when_all_empty(self):
        nodes = _nodes_from([_enterprise("e1", machinery="")])
        assert nodes.have_custom_machinery is False
