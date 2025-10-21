import json
import logging

import httpx
import pandas as pd
import requests

from config.settings.base import MG_EXPLORER_API_HOST
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

    pv_data = pd.read_json(json.dumps(parsed_response["data"]), orient="index")

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


def start_site_exploration(filter_data):
    """
    Send a request to the potential minigrid explorer with the given criteria. The exploration results must then be
    polled using the fetch_potential_sites function.
    Returns:
        exploration_id: ID to be used for results polling
    """
    request_url = MG_EXPLORER_API_HOST + "/explorations/"
    args = filter_data

    try:
        response = httpx.post(request_url, data=args, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred during the site exploration request."
        raise RuntimeError(msg) from e
    else:
        logger.info(
            "The exploration request was successfully sent to the potential minigrid explorer"
        )
        exploration_id = response.json()
        return exploration_id


def stop_site_exploration(exploration_id):
    """
    Send a request to the potential minigrid explorer to stop the exploration for the given id.
    """
    request_url = MG_EXPLORER_API_HOST + f"/explorations/{exploration_id}/stop"
    args = {
        "exploration_id": exploration_id,
    }

    try:
        response = httpx.post(request_url, data=args, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred during the site exploration stop request."
        raise RuntimeError(msg) from e
    else:
        logger.info(
            "The exploration stop request was successfully sent to the potential minigrid explorer"
        )
        return response.json()


def fetch_exploration_progress(exploration_id):
    """
    Send a GET request to fetch the progress of the potential minigrid exploration. While "status" is "RUNNING", the
    endpoint will keep returning more results as it is polled.
    """
    request_url = MG_EXPLORER_API_HOST + f"/explorations/{exploration_id}"

    try:
        response = httpx.get(request_url, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        # Retry exploration instead of raising an error
        logger.exception("HTTP error occurred")
        msg = "An error occurred during the site exploration results fetching. Retrying in 10 seconds."
        logger.info(msg)
        return {"status": "RUNNING", "minigrids": []}
    else:
        logger.info(
            "The exploration progress for ID %s was successfully fetched.",
            exploration_id,
        )
        return response.json()


def fetch_existing_minigrids():
    """
    Send a GET request to fetch the existing minigrids. When a new minigrid is planned, notify_existing_minigrids should
    be called to include the new minigrid in the existing minigrid list.
    """
    request_url = MG_EXPLORER_API_HOST + "/features/minigrids"

    try:
        response = httpx.get(request_url, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred while fetching existing minigrids."
        raise RuntimeError(msg) from e
    else:
        logger.info("Successfully fetched existing minigrid information.")
        return response.json()


def notify_existing_minigrids(new_mg_data):
    """
    Send a POST request to add the new minigrid to the existing minigrids data.
    """
    request_url = MG_EXPLORER_API_HOST + "/features/minigrids"
    args = new_mg_data

    try:
        response = httpx.post(request_url, data=args, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred while notifying the minigrid."
        raise RuntimeError(msg) from e
    else:
        logger.info("The existing minigrid list has been successfully updated.")
        return response.json()


def fetch_potential_minigrid_data(exploration_id, potential_minigrid_id):
    """
    Fetch the data for a potential minigrid site returned in the simulation. This information is then used to populate
    the steps for the site analysis.
    """
    request_url = (
        MG_EXPLORER_API_HOST
        + f"/explorations/{exploration_id}/minigrids/{potential_minigrid_id}"
    )

    try:
        response = httpx.get(request_url, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred during the minigrid data fetching."
        raise RuntimeError(msg) from e
    else:
        logger.info("Obtained data to populate project steps.")
        return response.json()


def fetch_buildings_data(bbox):
    """
    Fetch the building data for display on the map.
    """
    request_url = MG_EXPLORER_API_HOST + "/features/buildings"

    try:
        response = httpx.get(
            request_url, params={"bbox": ",".join(map(str, bbox))}, timeout=5
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred during the building data fetching."
        raise RuntimeError(msg) from e
    else:
        logger.info("Obtained building data data.")
        return response.json()


def fetch_grid_network():
    """
    Fetch the grid network for display on the map.
    """
    request_url = MG_EXPLORER_API_HOST + "/explorations/grid"

    try:
        response = httpx.get(request_url, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred during the grid data fetching."
        raise RuntimeError(msg) from e
    else:
        logger.info("Obtained grid network data.")
        return response.json()


def fetch_road_network():
    """
    Fetch the road network for display on the map.
    """
    request_url = MG_EXPLORER_API_HOST + "/explorations/roads"

    try:
        response = httpx.get(request_url, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.exception("HTTP error occurred")
        msg = "An error occurred during the road data fetching."
        raise RuntimeError(msg) from e
    else:
        logger.info("Obtained road network data.")
        return response.json()
