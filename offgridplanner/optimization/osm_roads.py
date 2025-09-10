# optimization/osm_roads.py
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_roads_from_overpass(bbox):
    """
    bbox: (south, west, north, east)
    Gets roads of any type from OSM.
    """
    query = f"""
    [out:json][timeout:25];
    (
      way["highway"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
    );
    out geom;
    """

    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    features = []
    for el in data.get("elements", []):
        if el.get("type") == "way" and "geometry" in el:
            coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"id": el.get("id")},
                }
            )

    return {"type": "FeatureCollection", "features": features}
