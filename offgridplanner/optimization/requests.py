import json
import logging

import httpx

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
    except httpx.HTTPError:
        logger.exception("HTTP error occurred")
        return None
    except Exception:
        logger.exception("Other error occurred")
        return None
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
