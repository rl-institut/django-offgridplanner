import io

import pandas as pd

from offgridplanner.projects.models import Options
from offgridplanner.projects.models import Project


def load_project_from_dict(model_data, user=None):
    """Create a new project for a user

    Parameters
    ----------
    model_data: dict
        output produced by the export() method of the Project model
    user: users.models.CustomUser
        the user which loads the scenario
    """
    options_data_dm = model_data.pop("options_data", None)

    model_data["user"] = user
    if options_data_dm is not None:
        options_data = Options(**options_data_dm)
        options_data.save()
        model_data["options"] = options_data
    project = Project(**model_data)
    project.save()

    return project.id


def df_to_file(df, file_type):
    if file_type == "xlsx":
        output = io.BytesIO()
        df.to_excel(output, index=False, engine="xlsxwriter")
        output.seek(0)
        return io.BytesIO(output.getvalue())
    if file_type == "csv":
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return io.StringIO(output.getvalue())


def is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def format_column_names(df):
    # TODO check and fix later
    df.columns = [str(col).replace("_", " ").capitalize() for col in df.columns]
    return df


def prepare_data_for_export(dataframes):
    # TODO check and fix later
    """
    Prepares dataframes for export by formatting columns, adding units, and renaming fields.
    """
    input_df = dataframes["user specified input parameters"]
    energy_system_design = dataframes["energy system design"]
    nodes_df = dataframes["nodes"]
    links_df = dataframes["links"]
    energy_flow_df = dataframes["energy flow"]
    results_df = dataframes["results"]

    # Merge input data and rename columns
    input_df = pd.concat([input_df.T, energy_system_design.T])
    input_df.columns = ["User specified input parameters"]
    input_df.index.name = ""
    input_df = input_df.rename(
        index={"shs_max_grid_cost": "shs_max_specific_marginal_grid_cost"}
    )
    input_df = input_df.drop(["status", "temporal_resolution"], errors="ignore")

    # Clean nodes and links data
    nodes_df = nodes_df.drop(
        columns=[
            col for col in ["distribution_cost", "parent"] if col in nodes_df.columns
        ]
    )

    if not links_df.empty:
        links_df = links_df[
            ["link_type", "length", "lat_from", "lon_from", "lat_to", "lon_to"]
        ]

    # TODO Format columns, add units
    dfs = [input_df, energy_flow_df, results_df, nodes_df, links_df]
    dfs = [format_column_names(df.reset_index()) for df in dfs]
    input_df, energy_flow_df, results_df, nodes_df, links_df = dfs

    return input_df, energy_flow_df, results_df, nodes_df, links_df
