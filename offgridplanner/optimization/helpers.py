import io
import os

import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError
from django.http import JsonResponse

from offgridplanner.projects.helpers import df_to_file


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
        "consumer_detail": {
            "Food_Groceries",
            "Food_Restaurant",
            "Food_Bar",
            "Food_Drinks",
            "Food_Fruits or vegetables",
            "Trades_Tailoring",
            "Trades_Beauty or Hair",
            "Trades_Metalworks",
            "Trades_Car or Motorbike Repair",
            "Trades_Carpentry",
            "Trades_Laundry",
            "Trades_Cycle Repair",
            "Trades_Shoemaking",
            "Retail_Medical",
            "Retail_Clothes and accessories",
            "Retail_Electronics",
            "Retail_Other",
            "Retail_Agricultural",
            "Digital_Mobile or Electronics Repair",
            "Digital_Digital Other",
            "Digital_Cybercafé",
            "Digital_Cinema or Betting",
            "Digital_Photostudio",
            "Agricultural_Mill or Thresher or Grater",
            "Agricultural_Other",
            "",
            "default",
            "Health_Health Centre",
            "Health_Clinic",
            "Health_CHPS",
            "Education_School",
            "Education_School_noICT",
        },
        "custom_specification": {
            "Milling Machine (7.5kW)",
            "Crop Dryer (8kW)",
            "Thresher (8kW)",
            "Grinder (5.2kW)",
            "Sawmill (2.25kW)",
            "Circular Wood Saw (1.5kW)",
            "Jigsaw (0.4kW)",
            "Drill (0.4kW)",
            "Welder (5.25kW)",
            "Angle Grinder (2kW)",
            "",
        },
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


def check_geographic_bounds(df):
    max_distance = float(os.environ.get("MAX_LAT_LON_DIST", 0.15))
    if (
        df["latitude"].max() - df["latitude"].min() > max_distance
        or df["longitude"].max() - df["longitude"].min() > max_distance
    ):
        error_msg = "Distance between consumers exceeds maximum allowed distance."
        raise ValidationError(error_msg)

    nigeria_bounds = {
        "latitude_min": 4.2,
        "latitude_max": 13.9,
        "longitude_min": 2.7,
        "longitude_max": 14.7,
    }
    out_of_bounds = df[
        (df["latitude"] < nigeria_bounds["latitude_min"])
        | (df["latitude"] > nigeria_bounds["latitude_max"])
        | (df["longitude"] < nigeria_bounds["longitude_min"])
        | (df["longitude"] > nigeria_bounds["longitude_max"])
    ]
    if not out_of_bounds.empty:
        error_msg = "Some latitude/longitude values are outside the bounds of Nigeria."
        raise ValidationError(error_msg)


def check_imported_consumer_data(df):
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
            processed_loads = [
                (
                    load.split(" x ", 1)[1]
                    if " x " in load and load[0].isdigit()
                    else load
                )
                for load in custom_loads
            ]
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
    check_geographic_bounds(df)
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


GRID_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["nodes", "grid_design", "yearly_demand"],
    "properties": {
        "nodes": {
            "type": "object",
            "required": [
                "latitude",
                "longitude",
                "how_added",
                "node_type",
                "consumer_type",
                "custom_specification",
                "shs_options",
                "consumer_detail",
                "is_connected",
            ],
            "properties": {
                "latitude": {
                    "type": "array",
                    "items": {"type": "number"},
                },
                "longitude": {
                    "type": "array",
                    "items": {"type": "number"},
                },
                "how_added": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "node_type": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "consumer_type": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "custom_specification": {
                    "type": "array",
                    "items": {"type": ["string", "null"]},
                },
                "shs_options": {
                    "type": "array",
                    "items": {"type": "number"},
                },
                "consumer_detail": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "is_connected": {
                    "type": "array",
                    "items": {"type": "boolean"},
                },
                "distance_to_load_center": {
                    "type": "array",
                    "items": {"type": "number"},
                },
                "distribution_cost": {
                    "type": "array",
                    "items": {"type": "number"},
                },
                "parent": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        "grid_design": {
            "type": "object",
            "required": ["distribution_cable", "connection_cable", "pole", "mg", "shs"],
            "properties": {
                "distribution_cable": {
                    "type": "object",
                    "required": ["capex", "max_length", "epc"],
                    "properties": {
                        "capex": {"type": "number"},
                        "max_length": {"type": "number"},
                        "epc": {"type": "number"},
                    },
                },
                "connection_cable": {
                    "type": "object",
                    "required": ["capex", "max_length", "epc"],
                    "properties": {
                        "capex": {"type": "number"},
                        "max_length": {"type": "number"},
                        "epc": {"type": "number"},
                    },
                },
                "pole": {
                    "type": "object",
                    "required": ["capex", "max_n_connections", "epc"],
                    "properties": {
                        "capex": {"type": "number"},
                        "max_n_connections": {"type": "integer"},
                        "epc": {"type": "number"},
                    },
                },
                "mg": {
                    "type": "object",
                    "required": ["connection_cost", "epc"],
                    "properties": {
                        "connection_cost": {"type": "number"},
                        "epc": {"type": "number"},
                    },
                },
                "shs": {
                    "type": "object",
                    "required": ["include", "max_grid_cost"],
                    "properties": {
                        "include": {"type": "boolean"},
                        "max_grid_cost": {"type": "number"},
                    },
                },
            },
        },
        "yearly_demand": {"type": "number"},
    },
    "additionalProperties": False,
}

GRID_V2_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["node_fields", "nodes", "grid_design", "yearly_demand"],
    "properties": {
        "node_fields": {"type": "array", "items": {"type": "string"}},
        "nodes": {
            "type": "array",
            "items": {
                "type": "array",
                "items": [
                    {"type": "integer"},  # id
                    {"type": "string", "enum": ["automatic", "k-means"]},  # how_added
                    {
                        "type": "string",
                        "enum": ["consumer", "power-house"],
                    },  # node_type
                    {
                        "type": "string",
                        "enum": ["enterprise", "household", "n.a.", "public_service"],
                    },  # consumer_type
                    {"type": "string"},  # custom_specification
                    {"type": "integer", "enum": [0]},  # shs_options
                    {
                        "type": "string",
                        "enum": [
                            "Education_School",
                            "Food_Bar",
                            "Food_Drinks",
                            "Health_CHPS",
                            "Retail_Other",
                            "Trades_Beauty or Hair",
                            "Trades_Car or Motorbike Repair",
                            "default",
                            "n.a.",
                        ],
                    },  # consumer_detail
                    {"type": "boolean"},  # is_connected
                    {
                        "type": "array",  # coordinates
                        "items": [
                            {"type": "number"},  # latitude
                            {"type": "number"},  # longitude
                        ],
                        "minItems": 2,
                        "maxItems": 2,
                    },
                ],
                "minItems": 9,
                "maxItems": 9,
            },
        },
        "grid_design": {
            "type": "object",
            "properties": {
                "distribution_cable": {
                    "type": "object",
                    "required": ["lifetime", "capex", "max_length", "epc"],
                    "properties": {
                        "lifetime": {"type": "integer"},
                        "capex": {"type": "number"},
                        "max_length": {"type": "number"},
                        "epc": {"type": "number"},
                    },
                },
                "connection_cable": {
                    "type": "object",
                    "required": ["lifetime", "capex", "max_length", "epc"],
                    "properties": {
                        "lifetime": {"type": "integer"},
                        "capex": {"type": "number"},
                        "max_length": {"type": "number"},
                        "epc": {"type": "number"},
                    },
                },
                "pole": {
                    "type": "object",
                    "required": ["lifetime", "capex", "max_n_connections", "epc"],
                    "properties": {
                        "lifetime": {"type": "integer"},
                        "capex": {"type": "number"},
                        "max_n_connections": {"type": "integer"},
                        "epc": {"type": "number"},
                    },
                },
                "mg": {
                    "type": "object",
                    "required": ["connection_cost", "epc"],
                    "properties": {
                        "connection_cost": {"type": "number"},
                        "epc": {"type": "number"},
                    },
                },
                "shs": {
                    "type": "object",
                    "required": ["include", "max_grid_cost"],
                    "properties": {
                        "include": {"type": "boolean"},
                        "max_grid_cost": {"type": "number"},
                    },
                },
            },
            "required": ["distribution_cable", "connection_cable", "pole", "mg", "shs"],
        },
        "yearly_demand": {"type": "number"},
    },
}


SUPPLY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "sequences": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "format": "date-time"},
                        "n_days": {"type": "integer", "minimum": 1},
                        "freq": {"type": "string", "enum": ["h"]},
                    },
                    "required": ["start_date", "n_days", "freq"],
                },
                "demand": {"type": "array", "items": {"type": "number"}},
                "solar_potential": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["index", "demand", "solar_potential"],
        },
        "energy_system_design": {
            "type": "object",
            "properties": {
                "battery": {"$ref": "#/definitions/component"},
                "diesel_genset": {"$ref": "#/definitions/component"},
                "inverter": {"$ref": "#/definitions/component"},
                "pv": {"$ref": "#/definitions/component"},
                "rectifier": {"$ref": "#/definitions/component"},
                "shortage": {
                    "type": "object",
                    "properties": {
                        "settings": {
                            "type": "object",
                            "properties": {"is_selected": {"type": "boolean"}},
                            "required": ["is_selected"],
                        },
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "max_shortage_total": {"type": "number"},
                                "max_shortage_timestep": {"type": "number"},
                                "shortage_penalty_cost": {"type": "number"},
                            },
                            "required": [
                                "max_shortage_total",
                                "max_shortage_timestep",
                                "shortage_penalty_cost",
                            ],
                        },
                    },
                    "required": ["settings", "parameters"],
                },
            },
            "required": [
                "battery",
                "diesel_genset",
                "inverter",
                "pv",
                "rectifier",
                "shortage",
            ],
        },
    },
    "required": ["sequences", "energy_system_design"],
    "definitions": {
        "component": {
            "type": "object",
            "properties": {
                "settings": {
                    "type": "object",
                    "properties": {
                        "is_selected": {"type": "boolean"},
                        "design": {"type": "boolean"},
                    },
                    "required": ["is_selected", "design"],
                },
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nominal_capacity": {"type": ["number", "null"]},
                        "soc_min": {"type": "number"},
                        "soc_max": {"type": "number"},
                        "c_rate_in": {"type": "number"},
                        "c_rate_out": {"type": "number"},
                        "efficiency": {"type": "number"},
                        "epc": {"type": "number"},
                        "variable_cost": {"type": "number"},
                        "fuel_cost": {"type": "number"},
                        "fuel_lhv": {"type": "number"},
                        "min_load": {"type": "number"},
                        "max_load": {"type": "number"},
                        "min_efficiency": {"type": "number"},
                        "max_efficiency": {"type": "number"},
                    },
                    "additionalProperties": True,
                },
            },
            "required": ["settings", "parameters"],
        }
    },
}
