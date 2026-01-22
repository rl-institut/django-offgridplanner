import io
import logging
import os

import numpy as np
import pandas as pd
import pycountry
from country_bounding_boxes import country_subunits_by_iso_code
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from rest_framework.generics import get_object_or_404

from config.settings.base import DEFAULT_COUNTRY
from offgridplanner.optimization.models import Results
from offgridplanner.optimization.processing import GridProcessor
from offgridplanner.optimization.processing import SupplyProcessor
from offgridplanner.optimization.supply.demand_estimation import ENTERPRISE_LIST
from offgridplanner.optimization.supply.demand_estimation import LARGE_LOAD_KW_MAPPING
from offgridplanner.optimization.supply.demand_estimation import LARGE_LOAD_LIST
from offgridplanner.optimization.supply.demand_estimation import PUBLIC_SERVICE_LIST
from offgridplanner.projects.models import Project

logger = logging.getLogger(__name__)


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
    else:
        err = f"File type .{file_type} not supported"
        raise ValueError(err)


def validate_file_extension(filename):
    allowed_extensions = ["csv", "xlsx"]
    file_extension = filename.split(".")[-1].lower()
    if file_extension not in allowed_extensions:
        return False, "Unsupported file type. Please upload a CSV or Excel file."
    return True, file_extension


def convert_file_to_df(file, file_extension):
    try:
        if file_extension == "csv":
            decoded_content = file.read().decode("utf-8")
            df = pd.read_csv(io.StringIO(decoded_content))
        else:  # "xlsx"
            df = pd.read_excel(io.BytesIO(file.read()), engine="openpyxl")

    except UnicodeDecodeError:
        return JsonResponse(
            {"responseMsg": "File encoding error. Please check the file format."},
            status=400,
        )
    except pd.errors.ParserError:
        return JsonResponse(
            {"responseMsg": "Error parsing the file. Ensure it is properly formatted."},
            status=400,
        )
    except OSError as e:
        return JsonResponse(
            {"responseMsg": f"File read/write error: {e!s}"}, status=500
        )

    if df.empty:
        return JsonResponse({"responseMsg": "Uploaded file is empty."}, status=400)
    return df


def check_missing_columns(df, required_columns):
    df.columns = [col.strip().lower() for col in df.columns]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        error = f"Missing required columns: {missing_columns}"
        raise ValidationError(error)


def set_default_values(df, defaults):
    df = df.replace("", np.nan)
    for col, val in defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(val)
    return df


def validate_column_inputs(input_values, column):
    # TODO get these directly from load profiles instead of manual
    allowed_values = {
        "consumer_type": {"household", "enterprise", "public_service"},
        "shs_options": {0, 1},
        "consumer_detail": {"", "default"}
        | set(ENTERPRISE_LIST)
        | set(PUBLIC_SERVICE_LIST),
        "custom_specification": {
            f"{machine} ({LARGE_LOAD_KW_MAPPING[machine]}kW)"
            for machine in LARGE_LOAD_LIST
        }
        | {""},
    }
    invalid_values = set(input_values) - allowed_values[column]
    if invalid_values:
        error = f"Invalid consumer_type values: {list(invalid_values)}. Allowed: {allowed_values[column]}"
        raise ValidationError(error)


def convert_column_types(df, column_types):
    for col, dtype in column_types.items():
        try:
            df[col] = df[col].astype(dtype)
        except ValueError as e:
            error = f"Error converting '{col}' to {dtype.__name__}: {e}"
            raise ValidationError(error) from e
    return df


def get_country_bounds(proj_id):
    project = get_object_or_404(Project, id=proj_id)

    country = project.country
    country_verbose = pycountry.countries.get(alpha_2=country).name
    country_info = country_subunits_by_iso_code(country)
    bboxes = {c.subunit: c.bbox for c in country_info}

    # Pick the bounding box that encompasses the country and not one of its subunits
    try:
        bbox = bboxes[country_verbose]
    except KeyError:
        logger.warning(
            "An error occurred fetching bounding box data. Either no data was returned, or an error occurred "
            "fetching entire country bounds instead of sub-units. Defaulting to %s bounds",
            DEFAULT_COUNTRY[1],
        )
        country_info = country_subunits_by_iso_code(DEFAULT_COUNTRY[0])
        bboxes = {c.subunit: c.bbox for c in country_info}
        bbox = bboxes[DEFAULT_COUNTRY[1]]

    bounds_data = {
        "longitude_min": bbox[0],
        "latitude_min": bbox[1],
        "longitude_max": bbox[2],
        "latitude_max": bbox[3],
    }

    return bounds_data


def check_geographic_bounds(df, proj_id):
    max_distance = float(os.environ.get("MAX_LAT_LON_DIST", 0.15))
    if (
        df["latitude"].max() - df["latitude"].min() > max_distance
        or df["longitude"].max() - df["longitude"].min() > max_distance
    ):
        error_msg = "Distance between consumers exceeds maximum allowed distance."
        raise ValidationError(error_msg)

    country_bounds = get_country_bounds(proj_id)
    out_of_bounds = df[
        (df["latitude"] < country_bounds["latitude_min"])
        | (df["latitude"] > country_bounds["latitude_max"])
        | (df["longitude"] < country_bounds["longitude_min"])
        | (df["longitude"] > country_bounds["longitude_max"])
    ]
    if not out_of_bounds.empty:
        error_msg = (
            "Some latitude/longitude values are outside the selected country bounds."
        )
        raise ValidationError(error_msg)


def check_imported_consumer_data(df, proj_id):
    """Validate imported consumer data."""
    if df.empty:
        error = "No data could be read."
        raise ValidationError(error)

    check_missing_columns(df, required_columns=["latitude", "longitude"])
    # Default values
    defaults = {
        "consumer_detail": "",
        "consumer_type": "household",
        "custom_specification": "",
        "shs_options": 0,
    }
    df = set_default_values(df, defaults)
    df["is_connected"], df["how_added"], df["node_type"] = True, "automatic", "consumer"
    # Validate column inputs
    for col in [
        "consumer_type",
        "shs_options",
        "consumer_detail",
        "custom_specification",
    ]:
        if col == "custom_specification":
            custom_loads = df.loc[df[col] != "", col].tolist()
            processed_loads = []
            for entry in custom_loads:
                # split if multiple machinery entries in one enterprise
                machinery = entry.split(";")
                # separate machine name for validation
                processed_entry = [
                    (
                        load.split(" x ", 1)[1]
                        if " x " in load and load[0].isdigit()
                        else load
                    )
                    for load in machinery
                ]
                # add to processed loads list
                processed_loads.extend(processed_entry)
            validate_column_inputs(processed_loads, col)
        else:
            validate_column_inputs(set(df[col]), col)

    # Convert column types
    column_types = {
        "latitude": float,
        "longitude": float,
        "shs_options": int,
        "consumer_type": str,
        "custom_specification": str,
        "is_connected": bool,
    }
    convert_column_types(df, column_types)
    # Check geographic bounds
    check_geographic_bounds(df, proj_id)
    df = df[
        [
            "latitude",
            "longitude",
            "how_added",
            "node_type",
            "consumer_type",
            "custom_specification",
            "shs_options",
            "consumer_detail",
            "is_connected",
        ]
    ]

    return df, ""


def consumer_data_to_file(df, file_type):
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "latitude",
                "longitude",
                "consumer_type",
                "custom_specification",
                "shs_options",
                "consumer_detail",
            ],
        )
    else:
        df = df.drop(columns=["is_connected", "how_added", "node_type"])
    return df_to_file(df, file_type)


def check_imported_demand_data(df, project_dict):
    if df.empty:
        return None, "No data could be read."

    df.columns = [col.strip().lower() for col in df.columns]
    if "demand" not in df.columns:
        return None, "Column with title 'demand' is missing."

    df = df["demand"].dropna()
    try:
        df = df.astype(float)
    except ValueError as e:
        return None, f"Error converting demand to float: {e!s}"

    n_days = min(project_dict["n_days"], int(os.environ.get("MAX_DAYS", 365)))
    ts = pd.Series(
        pd.date_range(
            pd.to_datetime("2022").to_pydatetime(),
            pd.to_datetime("2022").to_pydatetime() + pd.to_timedelta(n_days, unit="D"),
            freq="h",
            inclusive="left",
        )
    )
    if len(df) < len(ts):
        start_date_str = project_dict["start_date"].strftime("%d. %B %H:%M")
        return None, (
            f"You specified a start date of {start_date_str} and a simulation period of {n_days} days with an "
            f"hourly frequency, which requires {len(ts.index)} data points. However, only {len(df.index)} data points were provided."
        )

    df.index = ts.to_numpy()[: len(df.index)]
    return df.to_frame("demand"), ""


def process_optimization_results(proj_id, sim_res):
    grid_processor = GridProcessor(proj_id=proj_id, results_json=sim_res.get("grid"))
    grid_processor.grid_results_to_db()
    supply_processor = SupplyProcessor(
        proj_id=proj_id, results_json=sim_res.get("supply")
    )
    supply_processor.process_supply_optimization_results()
    supply_processor.supply_results_to_db()
    # Process shared results (after both grid and supply have been processed)
    results = Results.objects.get(simulation__project__id=proj_id)
    results.process_shared_results()
    results.save()
