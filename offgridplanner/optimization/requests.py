import json
import logging

import httpx
import pandas as pd

from config.settings.base import RN_API_HOST
from config.settings.base import RN_API_TOKEN
from config.settings.base import SIM_GET_URL
from config.settings.base import SIM_GRID_POST_URL
from config.settings.base import SIM_SUPPLY_POST_URL

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
        "tilt": lat,
        "azim": 180,
        "format": "json",
    }
    response = httpx.get(url, headers=headers, params=args)

    # Parse JSON to get a pandas.DataFrame of data and dict of metadata
    # import pdb; pdb.set_trace() # To be commented
    parsed_response = json.loads(response.text)

    pv_data = pd.read_json(json.dumps(parsed_response["data"]), orient="index")

    return pv_data
