import os

import numpy as np
import pandas as pd

from offgridplanner.projects.helpers import df_to_file


def check_imported_consumer_data(df):
    if df.empty:
        return None, "No data could be read."
    df.columns = [col.strip().lower() for col in df.columns]
    if "latitude" not in df.columns:
        return None, "Column with title 'latitude' is missing."
    if "longitude" not in df.columns:
        return None, "Column with title 'longitude' is missing."
    df["is_connected"] = True
    df["how_added"] = "automatic"
    df["node_type"] = "consumer"
    df = df.replace("", np.nan)
    df["consumer_detail"] = (
        df["consumer_detail"].fillna("") if "consumer_detail" in df.columns else ""
    )
    df["consumer_type"] = (
        df["consumer_type"].fillna("household")
        if "consumer_type" in df.columns
        else "household"
    )
    df["custom_specification"] = (
        df["custom_specification"].fillna("")
        if "custom_specification" in df.columns
        else ""
    )
    df["shs_options"] = (
        df["shs_options"].fillna(0) if "shs_options" in df.columns else 0
    )
    allowed_values = ["household", "enterprise", "public_service"]
    falsy_values = set(df["consumer_type"].unique()) - set(allowed_values)
    if len(falsy_values) > 0:
        return (
            None,
            f"Allowed values of column 'consumer_type' are {allowed_values}. Falsy values passed: {list(falsy_values)}.",
        )
    allowed_values_shs_option = [0, 1]
    falsy_values_shs_option = set(df["shs_options"].unique()) - set(
        allowed_values_shs_option,
    )
    if len(falsy_values_shs_option) > 0:
        return (
            None,
            f"Allowed values of column 'shs_options' are {allowed_values_shs_option}. Falsy values passed: {list(falsy_values_shs_option)}.",
        )
    # TODO get these directly from load profiles instead of manual
    valid_consumer_details = [
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
    ]

    valid_custom_specifications = [
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
    ]
    falsy_values_consumer_detail = set(df["consumer_detail"].unique()) - set(
        valid_consumer_details,
    )
    if len(falsy_values_consumer_detail) > 0:
        return (
            None,
            f"Allowed values of column 'consumer_detail' are {valid_consumer_details}. Falsy values passed: {list(falsy_values_consumer_detail)}.",
        )

    custom_loads = (
        df[df["custom_specification"] != ""]["custom_specification"].unique().tolist()
    )
    processed_loads = []
    non_matching_values = []
    for load in custom_loads:
        # If multiple custom loads separated by ";", split and append each
        if ";" in load:
            split_loads = load.split(";")
            custom_loads.extend(split_loads)
            custom_loads.remove(load)

    for load in custom_loads:
        if load[0].isdigit() and " x " in load:
            processed_loads.append(load.split(" x ", 1)[1])
        else:
            non_matching_values.append(load)
    if len(non_matching_values) > 0:
        return (
            None,
            f"Values of 'custom_specification' must start with an integer followed by \" x \"  {valid_custom_specifications}. Falsy values passed: {list(non_matching_values)}.",
        )
    falsy_values_custom_specification = set(processed_loads) - set(
        valid_custom_specifications,
    )
    if len(falsy_values_custom_specification) > 0:
        return (
            None,
            f"Allowed values of column 'custom_specification' are {valid_custom_specifications}. Falsy values passed: {list(falsy_values_custom_specification)}.",
        )
    columns_types = {
        "latitude": float,
        "longitude": float,
        "shs_options": int,
        "consumer_type": str,
        "custom_specification": str,
        "is_connected": bool,
    }
    for column, dtype in columns_types.items():
        try:
            df[column] = df[column].astype(dtype)
        except ValueError as e:
            return None, f"Error converting '{column}' to {dtype.__name__}: {e!s}"
    if df["latitude"].max() - df["latitude"].min() > float(
        os.environ.get("MAX_LAT_LON_DIST", 0.15),
    ) or df["longitude"].max() - df["longitude"].min() > float(
        os.environ.get("MAX_LAT_LON_DIST", 0.15),
    ):
        return None, "Distance between consumers exceeds maximum allowed distance."
    nigeria_bounds = {
        "latitude_min": 4.2,
        "latitude_max": 13.9,
        "longitude_min": 2.7,
        "longitude_max": 14.7,
    }
    out_of_bounds_latitudes = df[
        (df["latitude"] < nigeria_bounds["latitude_min"])
        | (df["latitude"] > nigeria_bounds["latitude_max"])
    ]
    out_of_bounds_longitudes = df[
        (df["longitude"] < nigeria_bounds["longitude_min"])
        | (df["longitude"] > nigeria_bounds["longitude_max"])
    ]
    if not out_of_bounds_latitudes.empty or not out_of_bounds_longitudes.empty:
        return None, (
            f"Error: Some latitude/longitude values are outside the bounds of Nigeria.\n"
            f"Latitude must be between {nigeria_bounds['latitude_min']} and {nigeria_bounds['latitude_max']}.\n"
            f"Longitude must be between {nigeria_bounds['longitude_min']} and {nigeria_bounds['longitude_max']}."
        )
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
