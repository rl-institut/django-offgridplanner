// osm-roads
function fetchOSMRoads(bbox) {
  const bboxStr = Array.isArray(bbox) ? bbox.join(",") : bbox;
  const url = `${osmRoadsUrl}?bbox=${encodeURIComponent(bboxStr)}`;

  return fetch(url, { headers: { "Accept": "application/json" } })
    .then(response => {
      if (!response.ok) {
        throw new Error(`fetchOSMRoads: HTTP ${response.status}`);
      }
      return response.json();
    })
    .catch(err => {
      console.error("fetchOSMRoads error:", err);
      throw err;
    });
}

window.fetchOSMRoads = fetchOSMRoads;

// customer_selection
function db_links_to_js() {
    fetch(dbLinksToJsUrl)
        .then(response => response.json())
        .then(links => {
            removeLinksFromMap(map);
            put_links_on_map(links);
        });
}

// customer_selection
async function db_nodes_to_js(proj_id, markers_only) {
    fetch(dbNodesToJsUrl + '/' + markers_only)
        .then(response => response.json())
        .then(data => {
            if (data !== null) {
                map_elements = data.map_elements;
                is_load_center = data.is_load_center;

                if (map_elements !== null) {
                    put_markers_on_map(map_elements, markers_only);
                }

            } else {
                map_elements = [];
                put_markers_on_map(map_elements, markers_only);
            }
        });
}

// customer_selection
async function file_nodes_to_js(formData) {
    try {
        const response = await fetch(fileNodesToJsUrl, {
            headers: {'X-CSRFToken': csrfToken },
            method: 'POST',
            body: formData
        });

        let result = null;
        try {
            result = await response.json();
        } catch (e) {
            console.error('Could not parse JSON:', e);
        }
        document.getElementById('responseMsg').innerHTML = '';
        document.getElementById('msgBox').style.display = 'none';

        if (response.ok && result !== null && 'map_elements' in result) {
            map_elements = result.map_elements;
            is_load_center = result.is_load_center;
            load_legend();
            if (map_elements !== null) {
                put_markers_on_map(map_elements, markers_only=true);
            }
        } else if (result !== null && 'responseMsg' in result) {
            document.getElementById('responseMsg').innerHTML = result.responseMsg;
            document.getElementById('msgBox').style.display = 'block';
        } else {
            console.error('File upload failed with status:', response.status);
        }
    } catch (error) {
        console.error('Error occurred during file upload:', error);
    }
}

// osm roads
async function db_roads_to_js(proj_id) {
    try {
        const response = await fetch(dbRoadsToJsUrl);
        const data = await response.json();

        if (data !== null) {
            road_elements = data.road_elements || [];
            if (road_elements.length > 0) {
                put_roads_on_map(road_elements);
            }
        } else {
            road_elements = [];
            put_roads_on_map([]);
        }
    } catch (err) {
        console.error("Error loading roads from DB:", err);
    }
}

// customer_selection
async function consumer_to_db(href, file_type = "db") {
    check_map_elements();
    const response = await fetch(consumerToDBUrl , {
        method: "POST",
        headers: {"Content-Type": "application/json", 'X-CSRFToken': csrfToken},
        body: JSON.stringify({map_elements: map_elements, file_type: file_type})
    });

    if (response.ok) {
        if (file_type === "db") {
            if (!href) {
                forward_if_consumer_selection_exists(project_id);
            } else if (href) {
                let updatedHref;
                // Check if 'steps' and 'href' are defined
                if (typeof steps !== 'undefined' && typeof href !== 'undefined') {
                    const stepsJson = encodeURIComponent(JSON.stringify(steps));
                    const separator = href.includes('?') ? '&' : '?';
                    updatedHref = `${href}${separator}steps=${stepsJson}`;
                } else {
                    updatedHref = href;
                }
                window.location.href = updatedHref;
            }
        } else {
            // Handle the file download for "csv" or "xlsx"
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = file_type === "xlsx" ? "offgridplanner_consumers.xlsx" : "offgridplanner_consumers.csv";
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(downloadUrl);
        }
    } else {
        resp = await response.json()
        document.getElementById('responseMsg').innerHTML = resp.message;
        document.getElementById('msgBox').style.display = 'block';
    }
}

async function roads_to_db(href, file_type = "db") {
    const response = await fetch(roadsToDBUrl, {
        method: "POST",
        headers: {"Content-Type": "application/json", 'X-CSRFToken': csrfToken},
        body: JSON.stringify({ road_elements: road_elements, file_type: file_type })
    });

    if (response.ok) {
        if (file_type === "db") {
            if (href) {
                window.location.href = href;
            }
        } else {
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = file_type === "xlsx" ? "roads.xlsx" : "roads.csv";
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(downloadUrl);
        }
    } else {
        console.error('Request failed with status:', response.status);
    }
}

function add_buildings_inside_boundary({boundariesCoordinates} = {}) {
    $("*").css("cursor", "wait");
    fetch(addBuildingsUrl, {
        method: "POST",
        headers: {"Content-Type": "application/json",'X-CSRFToken': csrfToken},
        body: JSON.stringify({boundary_coordinates: boundariesCoordinates, map_elements: map_elements,}),
    })
        .then((response) => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error("Failed to fetch data");
            }
        })
        .then((res) => {
            $("*").css('cursor', 'auto');
            const responseMsg = document.getElementById("responseMsg");
            responseMsg.innerHTML = res.msg;
            if (res.executed === false) {
            } else {
                responseMsg.innerHTML = "";
                Array.prototype.push.apply(map_elements, res.new_consumers);
                put_markers_on_map(res.new_consumers, true);
            }
            unique_map_elements();
        })
        .catch((error) => {
            console.error("Error fetching data:", error);
        });
}

function add_roads_inside_boundary({boundariesCoordinates} = {}) {
    $("*").css("cursor", "wait");
    fetch(addRoadsUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ boundary_coordinates: boundariesCoordinates, road_elements }),
    })
        .then((response) => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error("Failed to fetch road data");
            }
        })
        .then((res) => {
            $("*").css("cursor", "auto");
            const responseMsg = document.getElementById("responseMsg");
            responseMsg.innerHTML = res.msg;

            if (res.executed) {
                responseMsg.innerHTML = "";
                road_elements = res.new_roads;
                put_roads_on_map(res.new_roads);
            }
        })
        .catch((error) => {
            console.error("Error fetching roads:", error);
        });
}

function put_roads_on_map(roads) {
    roads.forEach((road) => {
        const latlngs = road.coordinates.map(c => [c[0], c[1]]);
        const polyline = L.polyline(latlngs, { color: "#cc99ff", weight: 2 });
        drawnItems.addLayer(polyline);
    });
}

async function remove_buildings_inside_boundary({boundariesCoordinates} = {}) {
    $("*").css("cursor", "wait");

    try {
        const response = await fetch(removeBuildingsUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
                boundary_coordinates: boundariesCoordinates,
                map_elements: map_elements,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const res = await response.json();

        map_elements = res.map_elements;
        remove_marker_from_map();
        put_markers_on_map(map_elements, true);
    } catch (error) {
        console.error("There was a problem with the fetch operation:", error.message);
    } finally {
        $("*").css('cursor', 'auto');
    }
}

async function remove_roads_inside_boundary({boundariesCoordinates} = {}) {
    $("*").css("cursor", "wait");

    try {
        const response = await fetch(removeRoadsUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ boundary_coordinates: boundariesCoordinates, road_elements }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const res = await response.json();

        road_elements = res.road_elements;
        drawnItems.clearLayers();
        put_roads_on_map(road_elements);
    } catch (error) {
        console.error("Error removing roads:", error.message);
    } finally {
        $("*").css("cursor", "auto");
    }
}
