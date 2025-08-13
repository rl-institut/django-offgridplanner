import csv
import io
from collections import defaultdict
from pathlib import Path

import pandas as pd
from django.contrib.staticfiles.storage import staticfiles_storage
from django.template.loader import render_to_string

from offgridplanner.projects.models import Options
from offgridplanner.projects.models import Project


def format_exploration_sites_data(sites):
    """
    Takes the JSON from the site exploration API and fits the data into the corresponding geojson/table format to be
    displayed on the exploration site.
    Parameters:
        sites: JSON data from fetch_exploration_progress["minigrids"]
    Returns:
        geojson_data: Data to construct the map markers
        table_data: Data formatted into table_template.html
    """
    # generate geoJSON for map

    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": site["centroid"]["coordinates"],
            },
            "properties": {
                "name": site["id"],
            },
        }
        for site in sites
    ]

    # generate table HTML
    context = {"sites": sites}
    table = render_to_string("widgets/table_template.html", context)
    return features, table


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


def from_nested_dict(model_cls, nested_data):
    """
    Convert a nested dict back to {field_name: value} for a Django model.
    """

    def flatten_dict(d, parent_key=""):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}__{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key))
            else:
                items.append((new_key, v))
        return items

    flat_items = flatten_dict(nested_data)

    # Map db_column -> field_name
    db_to_field = {
        field.db_column: field.name
        for field in model_cls._meta.fields
        if field.db_column
    }

    params = {}
    for db_column, value in flat_items:
        field_name = db_to_field.get(db_column)
        if not field_name:
            continue

        # Reverse the efficiency scaling
        if "efficiency" in db_column.split("__")[-1]:
            value *= 100

        params[field_name] = value

    return params


def csv_to_dict(filepath, label_col="label"):
    """
    Converts a CSV file into a nested dictionary using a specified label column as keys.

    Parameters:
        filepath (str): Path to the CSV file.
        label_col (str): Column name to be used as the dictionary key.

    Returns:
        dict: Nested dictionary where each row is stored under its label.
    """
    result = {}

    file_path = staticfiles_storage.path(filepath)
    if Path(file_path).exists():
        with Path(file_path).open(encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                label = row.pop(label_col)  # Remove label from row data
                result[label] = row  # Store remaining fields under this label

    return result


def convert_value(value, dtype):
    if value == "":
        return None

    if dtype == "float":
        return float(value)
    elif dtype == "int":
        return int(value)
    elif dtype == "bool":
        return bool(value)
    else:
        msg = f"Type {dtype} not supported"
        raise ValueError(msg)


def get_param_from_metadata(param, model=None):
    """
    Extracts a specific parameter for all fields in the given model (or all fields if None) from the
    FORM_FIELD_METADATA dictionary and returns a dictionary with {fields: values} for the parameter.

    Parameters:
        param (str): Parameter to extract from the nested dictionary
        model (str): Model by which to filter the fields

    Returns:
        dict: Field labels and the corresponding value for param
    """
    if model is not None:
        param_dict = {
            field: convert_value(
                FORM_FIELD_METADATA[field][param], FORM_FIELD_METADATA[field]["type"]
            )
            for field in FORM_FIELD_METADATA
            if FORM_FIELD_METADATA[field]["model"] == model
        }
    else:
        param_dict = {
            field: convert_value(
                FORM_FIELD_METADATA[field][param], FORM_FIELD_METADATA[field]["type"]
            )
            for field in FORM_FIELD_METADATA
        }

    return param_dict


def group_form_by_component(form):
    """Create a nested dictionary of form fields split by component. This assumes that the db_column of the model field
    is formatted with a double underscore as 'component_name__parameter_name'.
    Parameters:
        form (ModelForm): ModelForm containing all fields to be displayed

    Returns:
        grouped_fields (collections.defaultdict): Nested dictionary with component as keys and lists of (label, field) tuples as values
    """
    grouped_fields = defaultdict(list)
    for field_name, field in form.fields.items():
        component_name = field.db_column.split("__")[0]
        grouped_fields[component_name].append((field_name, form[field_name]))
    return grouped_fields


def reorder_dict(d, old_index, new_index):
    items = list(d.items())  # Convert dictionary to list of key-value pairs
    item = items.pop(old_index)  # Remove the item at the old index
    items.insert(new_index, item)  # Insert it at the new index
    return dict(items)


FORM_FIELD_METADATA = csv_to_dict("data/form_parameters.csv")
OUTPUT_KPIS = csv_to_dict("data/output_kpis.csv")
