import io
import json
import logging

import httpx
import pandas as pd
import requests

from config.settings.base import RN_API_HOST
from config.settings.base import RN_API_TOKEN
from config.settings.base import SIM_GET_URL
from config.settings.base import SIM_GRID_POST_URL
from config.settings.base import SIM_SUPPLY_POST_URL
from config.settings.base import WEATHER_DATA_API_HOST

logger = logging.getLogger(__name__)


def check_opt_type(opt_type: str):
    if opt_type not in ["grid", "supply"]:
        msg = 'Invalid simulation type, possible options are "grid" or "supply"'
        raise ValueError(msg)


def optimization_server_request(data: dict, opt_type: str):
    check_opt_type(opt_type)
    headers = {"content-type": "application/json"}
    payload = json.dumps(data)

    request_url = SIM_GRID_POST_URL if opt_type == "grid" else SIM_SUPPLY_POST_URL

    try:
        response = httpx.post(
            request_url,
            data=payload,
            headers=headers,
        )

        # If the response was successful, no Exception will be raised
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred during the optimization request."
        raise RuntimeError(msg) from e
    else:
        logger.info("The simulation was sent successfully to MVS API.")
        return json.loads(response.text)


def optimization_check_status(token):
    try:
        response = httpx.get(SIM_GET_URL + token)
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("HTTP error occurred")
        return None
    except Exception:
        logger.exception("Other error occurred")
        return None
    else:
        logger.info("Success!")
        return json.loads(response.text)


def request_renewables_ninja_pv_output(lat, lon):
    headers = {"Authorization": "Token " + RN_API_TOKEN}
    url = RN_API_HOST + "data/pv"

    args = {
        "lat": lat,
        "lon": lon,
        "date_from": "2019-01-01",
        "date_to": "2019-12-31",
        "dataset": "merra2",
        "capacity": 1.0,
        "system_loss": 0.1,
        "tracking": 0,
        "tilt": 30,
        "azim": 180,
        "format": "json",
    }
    response = httpx.get(url, headers=headers, params=args)

    # Parse JSON to get a pandas.DataFrame of data and dict of metadata
    parsed_response = json.loads(response.text)

    pv_data = pd.read_json(
        io.StringIO(json.dumps(parsed_response["data"])), orient="index"
    )

    return pv_data


def request_weather_data(latitude, longitude, *, timeinfo=False):
    session = requests.Session()

    # TODO one shouldn't need a csrftoken for server to server
    # fetch CSRF token
    csrf_response = session.get(WEATHER_DATA_API_HOST + "get_csrf_token/")
    csrftoken = csrf_response.json()["csrfToken"]

    payload = {"latitude": latitude, "longitude": longitude}

    # headers = {"content-type": "application/json"}
    headers = {
        "X-CSRFToken": csrftoken,
        "Referer": WEATHER_DATA_API_HOST,
    }

    post_response = session.post(WEATHER_DATA_API_HOST, data=payload, headers=headers)
    # TODO here would be best to return a token but this requires celery on the weather_data API side
    # If we get a high request amount we might need to do so anyway
    if post_response.ok:
        response_data = post_response.json()
        df = pd.DataFrame(response_data["variables"])
        logger.info("The weather data API fetch worked successfully")

        if timeinfo is True:
            timeindex = response_data["time"]
    else:
        df = pd.DataFrame()
        logger.error("The weather data API fetch did not work")

    if timeinfo is False:
        return df
    else:
        return df, timeindex
