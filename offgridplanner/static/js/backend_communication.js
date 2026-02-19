/**
 * This JavaScript file contains a collection of asynchronous functions designed to communicate
 * with a FastAPI backend server. These functions are integral to the operation of a web application,
 * enabling a wide range of interactive features and data-driven functionalities. Key aspects include:
 *
 * - Fetching and Rendering Data: Functions to retrieve various types of data from the server,
 *   such as plot data for charts, node and link data for maps, and results of energy system optimization.
 *   This data is then used to update the UI and render visualizations accordingly.
 *
 * - Form Submission and Data Handling: Several functions handle the submission of forms and user data
 *   to the server. This includes user registration, login, password changes, and deletion of accounts.
 *   Additionally, project-specific data like energy system design, grid design, and demand estimation are
 *   also submitted for processing and storage.
 *
 * - Dynamic UI Updates: Functions that dynamically update the user interface based on the data received
 *   from the server or user interactions. This includes updating map markers, displaying project details,
 *   and showing/hiding elements based on user actions or server responses.
 *
 * - User Authentication and Session Management: Functions to manage user sessions, including login,
 *   logout, token renewal, and handling anonymous sessions. This ensures secure access and personalization
 *   of the user experience.
 *
 * - Project Management: Functions to create, copy, and delete projects, as well as handling specific
 *   project-related tasks like starting calculations, checking for pending tasks, and managing notifications.
 *
 * - Utility Functions: Additional utility functions like captcha handling for security, cookie consent
 *   management, and email functionalities to enhance user interaction and application security.
 *
 * Overall, these functions form the backbone of client-server communication in the application, ensuring
 * smooth data flow, user interaction, and application functionality.
 */

$('.js-captcha-refresh').click(function(){
    $form = $(this).parents('form');
    $.getJSON($(this).data('url'), {}, function(json) {
        // Update image
        $form.find('img.captcha').attr('src', json.image_url);
        // Update hidden key
        $form.find('input[name="captcha_0"]').val(json.key);
        // Clear + focus text input
        $form.find('input[name="captcha_1"]').val('').focus();
    });
    return false;
});


async function plot_results(sequential = false) {
    const urlParams = new URLSearchParams(window.location.search);
    const project_id = urlParams.get('project_id');

    if (sequential) {
        // Sequential execution: wait for each fetch and plot to complete before starting the next

        // Fetch and plot 'other' data
        const response3 = await fetch(loadPlotDataUrl + '/other');
        const data3 = await response3.json();
        plot_lcoe_pie(data3.lcoe_breakdown);
        plot_bar_chart(data3.optimal_capacities);
        plot_sankey(data3.sankey_data);

        // Check if 'steps' exists and if steps[0] is true
        if (typeof steps !== 'undefined' && steps[0]) {
            // Proceed with fetching and plotting 'demand_24h' data
            const response6 = await fetch(loadDemandPlotUrl);
            const data6 = await response6.json();
            plot_demand_24h(data6);
        } else {
            // Hide the div with id 'demandtsChart'
            const demandTsChartDiv = document.getElementById('demandtsChart');
            if (demandTsChartDiv) {
                demandTsChartDiv.style.display = 'none';
            }
        }

        // Fetch and plot 'demand_coverage' data
        const response1 = await fetch(loadPlotDataUrl + '/demand_coverage');
        const data1 = await response1.json();
        plot_demand_coverage(data1.demand_coverage);

        // Fetch and plot 'energy_flow' data
        const response2 = await fetch(loadPlotDataUrl + '/energy_flow');
        const data2 = await response2.json();
        plot_energy_flows(data2.energy_flow);

        // Fetch and plot 'duration_curve' data
        const response4 = await fetch(loadPlotDataUrl + '/duration_curve');
        const data4 = await response4.json();
        plot_duration_curves(data4.duration_curve);

        // Fetch and plot 'emissions' data
        const response5 = await fetch(loadPlotDataUrl + '/emissions');
        const data5 = await response5.json();
        plot_co2_emissions(data5.emissions);

    } else {
        // Parallel execution: fetch data in parallel and plot as soon as each dataset is available

        // Initialize an array to hold fetch and plot promises
        const fetchAndPlotPromises = [];

        // Fetch and plot 'demand_coverage' data
        const fetchAndPlot1 = fetch(loadPlotDataUrl + '/demand_coverage')
            .then(response => response.json())
            .then(data => plot_demand_coverage(data.demand_coverage));
        fetchAndPlotPromises.push(fetchAndPlot1);

        // Fetch and plot 'energy_flow' data
        const fetchAndPlot2 = fetch(loadPlotDataUrl + '/energy_flow')
            .then(response => response.json())
            .then(data => plot_energy_flows(data.energy_flow));
        fetchAndPlotPromises.push(fetchAndPlot2);

        // Fetch and plot 'other' data
        const fetchAndPlot3 = fetch(loadPlotDataUrl + '/other')
            .then(response => response.json())
            .then(data => {
                plot_lcoe_pie(data.lcoe_breakdown);
                plot_bar_chart(data.optimal_capacities);
                plot_sankey(data.sankey_data);
            });
        fetchAndPlotPromises.push(fetchAndPlot3);

        // Fetch and plot 'duration_curve' data
        const fetchAndPlot4 = fetch(loadPlotDataUrl + '/duration_curve')
            .then(response => response.json())
            .then(data => plot_duration_curves(data.duration_curve));
        fetchAndPlotPromises.push(fetchAndPlot4);

        // Fetch and plot 'emissions' data
        const fetchAndPlot5 = fetch(loadPlotDataUrl + '/emissions')
            .then(response => response.json())
            .then(data => plot_co2_emissions(data.emissions));
        fetchAndPlotPromises.push(fetchAndPlot5);

        // Check if 'steps' exists and if steps[0] is true
        if (typeof steps !== 'undefined' && steps[0]) {
            // Proceed with fetching and plotting 'demand_24h' data
            const fetchAndPlot6 = fetch(loadDemandPlotUrl)
                .then(response => response.json())
                .then(data => plot_demand_24h(data));
            fetchAndPlotPromises.push(fetchAndPlot6);
        } else {
            // Hide the div with id 'demandtsChart'
            const demandTsChartDiv = document.getElementById('demandtsChart');
            if (demandTsChartDiv) {
                demandTsChartDiv.style.display = 'none';
            }
        }

        // Wait for all fetch and plot operations to complete (parallel execution)
        await Promise.all(fetchAndPlotPromises);
    }
}

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
        if (response.ok) {
            // todo check what this was supposed to do ...
            document.getElementById('responseMsg').innerHTML = '';
            document.getElementById('msgBox').style.display = 'none';
            const result = await response.json();
            if (result !== null && 'map_elements' in result) {
                map_elements = result.map_elements;
                is_load_center = result.is_load_center;
                load_legend();
                if (map_elements !== null) {
                    put_markers_on_map(map_elements, markers_only=true);
                }
            } else if (result !== null && 'responseMsg' in result) {
                document.getElementById('responseMsg').innerHTML = result.responseMsg;
                document.getElementById('msgBox').style.display = 'block';
            }
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

async function file_demand_to_db(formData) {
    try {
        const response = await fetch(importDemandUrl, {
            headers: {'X-CSRFToken': csrfToken },
            method: 'POST',
            body: formData
        });
        if (response.ok) {
            document.getElementById('responseMsg').innerHTML = '';
            document.getElementById('msgBox').style.display = 'none';
            document.getElementById('uploadStatus').textContent = 'Uploaded';
        } else {
            const result = await response.json();
            document.getElementById('responseMsg').innerHTML = result.responseMsg;
            document.getElementById('msgBox').style.display = 'block';
            document.getElementById('uploadStatus').textContent = 'Upload Failed';
        }
    } catch (error) {
        console.error('Error occurred during file upload:', error);
    }
}

// customer_selection
async function consumer_to_db(href, file_type = "db") {
    update_map_elements();
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
        console.error('Request failed with status:', response.status);
        const errorDetails = await response.json();
        console.error('Error details:', errorDetails);
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

// TODO move this to map related js, customer_selection
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

// TODO move this to map related js, customer_selection
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

let hasRetried = false;

async function load_results(project_id) {
    await db_nodes_to_js(markers_only=false);
    await plot_results();
    await db_roads_to_js(proj_id);
}


async function save_project_setup(href) {
    event.preventDefault(); // prevent the link from navigating immediately

    const toggleSwitch0 = document.getElementById('toggleswitch0');
    const toggleSwitch1 = document.getElementById('toggleswitch1');
    const toggleSwitch2 = document.getElementById('toggleswitch2');

    // Check if all toggle switches are unchecked
    if (!toggleSwitch0.checked && !toggleSwitch1.checked && !toggleSwitch2.checked) {
        // Update the text content of responseMsg
        document.getElementById('responseMsg').textContent =
            "You must select at least one planning step to proceed.";

        // Optionally show a modal or other feedback to the user
        document.getElementById('msgBox').style.display = 'block';
        return; // Exit the function to prevent fetching and navigation
    }

    const url = "save_project_setup/" + proj_id;
    const data = {
        page_setup: {
            'project_name': projectName.value,
            'project_description': projectDescription.value.trim(),
            'interest_rate': interestRate.value,
            'project_lifetime': projectLifetime.value,
            'start_date': "2022-01-01",
            'temporal_resolution': 1,
            'n_days': nDays.value,
            'do_demand_estimation': toggleSwitch0.checked,
            'do_grid_optimization': toggleSwitch1.checked,
            'do_es_design_optimization': toggleSwitch2.checked,
        }
    };

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            throw new Error("HTTP error " + response.status);
        }
        steps = [toggleSwitch0.checked, toggleSwitch1.checked, toggleSwitch2.checked];

        // Check if 'href' is defined and is a string
        if (typeof href === 'string') {
            const stepsJson = encodeURIComponent(JSON.stringify(steps));
            const separator = href.includes('?') ? '&' : '?';
            const updatedHref = `${href}${separator}steps=${stepsJson}`;
            window.location.href = updatedHref;
        } else {
            window.location.href = href;
        }
    } catch (err) {
        console.log("An error occurred while saving the project setup:", err);
    }
}


async function save_grid_design(href) {
    try {
        let shs_max_grid_cost_value;
        if (document.getElementById('shs_max_grid_cost').disabled) {
            shs_max_grid_cost_value = 999;
        } else {
            shs_max_grid_cost_value = document.getElementById('shs_max_grid_cost').value;
        }

        await fetch("save_grid_design/" + proj_id, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                grid_design: {
                    'distribution_cable_lifetime': distributionCableLifetime.value,
                    'distribution_cable_capex': distributionCableCapex.value,
                    'distribution_cable_max_length': distributionCableMaxLength.value,
                    'connection_cable_lifetime': connectionCableLifetime.value,
                    'connection_cable_capex': connectionCableCapex.value,
                    'connection_cable_max_length': connectionCableMaxLength.value,
                    'pole_lifetime': poleLifetime.value,
                    'pole_capex': poleCapex.value,
                    'pole_max_n_connections': poleMaxNumberOfConnections.value,
                    'mg_connection_cost': mgConnectionCost.value,
                    'shs_max_grid_cost': shs_max_grid_cost_value,
                }
            })
        });
        let updatedHref;
        // Check if 'steps' and 'href' are defined
        if (typeof steps !== 'undefined' && typeof href !== 'undefined') {
            const stepsJson = encodeURIComponent(JSON.stringify(steps));
            const separator = href.includes('?') ? '&' : '?';
            updatedHref = `${href}${separator}steps=${stepsJson}`;
        } else {
            updatedHref = href;
        }
        window.location.href = updatedHref; // navigate after fetch request is complete
    } catch (err) {
        console.log('Fetch API error -', err);
    }
}


function save_demand_estimation(href) {
    let custom_calibration = document.getElementById("toggleswitch").checked;
    const toggleSwitch = document.getElementById('toggleswitch2');
    const uploadStatus = document.getElementById('uploadStatus').textContent.trim();
    const useCustomDemand = toggleSwitch.checked && uploadStatus === "Uploaded";
    let updatedHref;

    // Conditional check for forwarding or displaying a modal
    if (!toggleSwitch.checked || useCustomDemand) {
        fetch("save_demand_estimation/" + proj_id, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                demand_estimation: {
                    'household_option': selectedValue,
                    'maximum_peak_load': maximum_peak_load.value,
                    'average_daily_energy': average_daily_energy.value,
                    'custom_calibration': custom_calibration,
                    'use_custom_shares': true,
                    'custom_share_1': custom_share_1.value,
                    'custom_share_2': custom_share_2.value,
                    'custom_share_3': custom_share_3.value,
                    'custom_share_4': custom_share_4.value,
                    'custom_share_5': custom_share_5.value,
                    'use_custom_demand': useCustomDemand,
                }
            })
        }).then(response => {
            // Check if 'steps' and 'href' are defined
            if (typeof steps !== 'undefined' && typeof href !== 'undefined') {
                const stepsJson = encodeURIComponent(JSON.stringify(steps));
                const separator = href.includes('?') ? '&' : '?';
                updatedHref = `${href}${separator}steps=${stepsJson}`;
            } else {
                updatedHref = href;
            }
            window.location.href = updatedHref;
        }).catch(error => {
            console.error('Error:', error);
        });
    } else {
        // Show modal with the translated and improved message
        const message = "Custom demand time series was selected, but no time series was successfully uploaded. Please upload a time series or disable this option to automatically calculate the demand time series.";
        document.getElementById('responseMsg').innerHTML = message;
        document.getElementById('msgBox').style.display = 'block';
    }
}


// TODO potentially useless as in django template one can get this information easily
async function show_email_and_project_in_navbar(project_id = null) {
    try {
        const response = await fetch("query_account_data/", {
            method: "POST",
            headers: {"Content-Type": "application/json", 'X-CSRFToken': csrfToken},
            body: JSON.stringify({'project_id': project_id}),
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const showMailElement = document.getElementById("showMail");
        const showProjectElement = document.getElementById("showProject");
        if (showMailElement) {
            showMailElement.innerHTML = data.email;
        }
        if (showProjectElement && data.project_name) {
            showProjectElement.innerHTML = "     Project: " + data.project_name;
        }
    } catch (error) {
        console.error("Error fetching account data:", error);
    }
}


let shouldStop = false;

async function wait_for_both_results(project_id, token_supply, token_grid) {
    const [supplyRes, gridRes] = await Promise.all([
        check_optimization(project_id, token_supply, 0, 'supply'),
        check_optimization(project_id, token_grid, 0, 'grid')
    ]);
    // Once both are finished, send results together for final processing
    const response = await fetch(processResultsUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            results: {
                supply: supplyRes.results,
                grid: gridRes.results
            }
        })
    });

    if (response.ok) {
        const lang_prefix = '/' + lang;
        window.location.href = window.location.origin + lang_prefix +'/steps/simulation_results/' + project_id;
    } else {
        console.error("Failed to process final results");
        window.location.href = "/?internal_error";
    }
}


async function check_optimization(project_id, token, time, model) {
    if (!window.location.href.includes("/calculating") || shouldStop) return;

    try {
        const response = await fetch(waitingForResultsUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ 'project_id': project_id, 'token': token, 'time': time, 'model': model })
        });

        if (response.ok) {
            const res = await response.json();
            if (res.status != "ERROR") {
                if (res.finished === true) {
                    return { results: res.results }; // Return the result for batch processing
                } else {
                    document.getElementById("statusMsg").innerHTML = `Waiting for ${model} optimization...`;
                    await new Promise(resolve => setTimeout(resolve, 10000)); // Wait 10 seconds
                    return await check_optimization(project_id, res.token, res.time, res.model);
                }
            } else {
                shouldStop = true;
                document.getElementById("loader").classList.remove("loader");
                document.getElementById("loader").classList.add("error-cross");
                document.getElementById("statusMsg").classList.add("There was an error fetching the optimization");
            }
        } else {
            if (response.status === 303 || response.status === 422) {
                shouldStop = true;
                window.location.href = "/?internal_error";
            }
        }
    } catch (error) {
        console.error("Fetch error:", error.message);
    }
}

async function forward_if_no_task_is_pending(project_id) {
    try {
        const response = await fetch("forward_if_no_task_is_pending/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken

            },
        });

        if (response.ok) {
            const res = await response.json();

            if (res.forward === true) {
                window.location.href = window.location.origin + '/steps/calculating/' + proj_id;
            } else {
                document.getElementById('pendingTask').style.display = 'block';
            }
        } else {
            console.error("Server responded with a status:", response.status);
        }
    } catch (error) {
        console.error("There was a problem with the fetch operation:", error.message);
    }
}


async function abort_calculation(proj_id) {
    try {
        const response = await fetch(abortCalculationUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            }
        });

        if (response.ok) {
            document.getElementById('pendingTask').style.display = 'none';
        } else {
            console.error("Server responded with a status:", response.status);
        }
    } catch (error) {
        console.error("There was a problem with the fetch operation:", error.message);
    }
}


function start_calculation(project_id) {
    fetch(startCalculationUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(res => {
        if (res.error && res.error.length > 0) {
            shouldStop = true;
            document.getElementById("loader").classList.remove("loader");
            document.getElementById("loader").classList.add("error-cross");
            document.getElementById("statusMsg").innerHTML = res.error;
        } else {
            wait_for_both_results(project_id, res.token_supply, res.token_grid);
        }
    })
    .catch(error => {
        shouldStop = true;
        document.getElementById("loader").classList.remove("loader");
        document.getElementById("loader").classList.add("error-cross");
        document.getElementById("statusMsg").innerHTML = "An error occurred";
        console.error('There was an error!', error);
    });
}


async function forward_if_consumer_selection_exists(project_id) {
    let href
    try {
        const response = await fetch("forward_if_consumer_selection_exists/" + proj_id, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            }
        });

        if (response.ok) {
            const res = await response.json();
            if (res.forward === true) {
                href = window.location.origin + '/demand_estimation?project_id=' + proj_id;
                let updatedHref;
                // Check if 'steps' and 'href' are defined
                if (typeof steps !== 'undefined' && typeof href !== 'undefined') {
                    const stepsJson = encodeURIComponent(JSON.stringify(steps));
                    const separator = href.includes('?') ? '&' : '?';
                    updatedHref = `${href}${separator}steps=${stepsJson}`;
                } else {
                    updatedHref = href;
                }
                window.location.href = updatedHref
            } else {
                document.getElementById('responseMsg').innerHTML = 'No consumers are selected. You must select the geolocation of the consumers before you go to the next page.';
            }
        } else {
            console.error("Server responded with a status:", response.status);
        }
    } catch (error) {
        console.error("There was a problem with the fetch operation:", error.message);
    }
}


async function send_email_notification(project_id, is_active) {
    try {
        const response = await fetch("/set_email_notification/" + proj_id + '/' + is_active, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            }
        });

        if (!response.ok) {
            console.error("Server responded with a status:", response.status);
        }
    } catch (error) {
        console.error("There was a problem with the fetch operation:", error.message);
    }
}


async function show_cookie_consent() {
    try {
        const response = await fetch("has_cookie/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({'access_token': false, 'consent_cookie': true})
        });

        const data = await response.json();

        if (data == false) {
            document.getElementById('consentCookie').style.display = 'block';
        } else {
            document.getElementById('consentCookie').style.display = 'none';
        }

    } catch (error) {
        console.error("There was a problem with the fetch operation:", error.message);
    }
}


async function send_reset_password_email() {
    try {
        const response = await fetch("send_reset_password_email/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                'email': userEmail4.value,
                'captcha_input': captcha_input.value,
                'hashed_captcha': hashedCaptcha
            })
        });

        const data = await response.json();

        document.getElementById("responseMsg4").innerHTML = data.msg;
        let fontcolor;
        if (data.validation === true) {
            fontcolor = 'green';
        } else {
            fontcolor = 'red';
        }
        document.getElementById("responseMsg4").style.color = fontcolor;

        if (data.validation === true) {
            await new Promise(r => setTimeout(r, 3000));
            document.getElementById('forgotPassword').style.display = 'none';
        }

    } catch (error) {
        console.error("There was a problem with the fetch operation:", error.message);
    }
}


function reset_pw(guid) {
    if (newUserPassword1.value !== newUserPassword2.value) {
        document.getElementById("responseMsg2").innerHTML = 'The passwords do not match';
        document.getElementById("responseMsg2").style.color = 'red';
        return;
    }

    fetch("reset_password", {
        method: "POST",
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            guid: guid,
            password: newUserPassword1.value
        })
    })
        .then(response => response.json())
        .then(async (data) => {
            document.getElementById("responseMsg2").innerHTML = data.msg;
            let fontcolor = data.validation ? 'green' : 'red';
            document.getElementById("responseMsg2").style.color = fontcolor;

            if (data.validation) {
                await new Promise(r => setTimeout(r, 3000));
                window.location.href = window.location.origin;
            }
        })
        .catch(error => {
            console.error("There was an error:", error);
        });
}


function create_example_project() {
    fetch("/example_model/")
        .then(res => {
            if (res.ok) {  // Check if the fetch was successful
                window.location.reload();  // Reload the page
            } else {
                console.error('Failed to fetch example model. Status:', res.status);
            }
        })
        .catch(err => {
            console.error('Error fetching example model:', err);
        });
}


function show_video_tutorial() {
    fetch("/show_video_tutorial/")
        .then(response => response.json())
        .then(res => {
            let show_tutorial = res;
            if (show_tutorial === true) {
                document.getElementById('videoTutorial').style.display = 'block';
            } else {
                document.getElementById('videoTutorial').style.display = 'none';
            }
        })
}

function deactivate_video_tutorial() {
    fetch("/deactivate_video_tutorial/")
}

function copyProject(url) {
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Failed to copy project');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred');
        });
}

// Initializes the help text tooltips (for the hover divs to be nicely formatted instead of default)
document.addEventListener('DOMContentLoaded', function () {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('.icon[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            trigger: 'hover click'
        });
    });
});


const img = document.getElementById("captcha_img");
const img2 = document.getElementById("captcha_img2");
const img3 = document.getElementById("captcha_img3");
let hashedCaptcha;

function get_captcha() {
    fetch(getCaptchaUrl)
        .then(response => response.json())
        .then(data => {
            img.src = "data:image/jpeg;base64," + data.img;
            img2.src = "data:image/jpeg;base64," + data.img;
            img3.src = "data:image/jpeg;base64," + data.img;
            hashedCaptcha = data.hashed_captcha;
        });
}


async function sendMail() {
    // Getting values from the HTML elements
    const from_address = document.getElementById("from_address").value;
    const subject = document.getElementById("subject").value;
    const body = document.getElementById("body").value;

    function handleError() {
        const responseMsgElement = document.getElementById("responseMsg");
        responseMsgElement.innerText = "Something went wrong";
        responseMsgElement.style.color = "red";
    }

    // Creating the mail object
    const mail = {
        from_address: from_address,
        subject: subject,
        body: body
    };

    // Reference to the responseMsg element
    const responseMsgElement = document.getElementById("responseMsg");

    // Sending the mail object to the FastAPI route
    try {
        const response = await fetch("/send_mail_route/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(mail)
        });

        if (response.status === 200) {
            const result = await response.json();
            if (result.message === "Success") {
                responseMsgElement.innerText = "Email successfully sent";
                responseMsgElement.style.color = "green";

                // Redirect to the base URL after 1.5 seconds
                setTimeout(() => {
                    window.location.href = "/";
                }, 2500);
            } else {
                handleError();
            }
        } else {
            handleError();
        }
    } catch (error) {
        handleError();
    }
}

// TODO could delete this function as this is handeled by django forms
async function update_wizards_and_buttons_based_on_planning_step_selection(project_id, page_name) {
    const nextButton = document.getElementById("nextButton");
    const prevButton = document.getElementById("prevButton");
    const wizardSection = document.getElementById('wizard');
    let results

    // Check if planning_steps is defined and is a dictionary
    if (typeof steps === 'object' && steps !== null) {
        results = {
            do_demand_estimation: steps[0],
            do_grid_optimization: steps[1],
            do_es_design_optimization: steps[2]
        };
    } else {
        const url = `load_previous_data/project_setup?project_id=${project_id}`;

        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            results = await response.json();
            steps = [results['do_demand_estimation'], results['do_grid_optimization'], results['do_es_design_optimization']]
        } catch (error) {
            console.error("Error fetching data:", error);
            return; // Exit the function if fetching data fails
        }
    }
    if (results !== null && Object.keys(results).length > 1) {
        if (page_name.includes("demand_estimation")) {
            if (results['do_grid_optimization'] === true && results['do_es_design_optimization'] === true) {
            } else if (results['do_grid_optimization'] === false && results['do_es_design_optimization'] === true) {
                nextButton.setAttribute('onclick', `save_demand_estimation(\`energy_system_design?project_id=${project_id}\`);`);
                if (results['do_demand_estimation'] === false) {
                    prevButton.setAttribute('onclick', `save_demand_estimation(\`project_setup?project_id=${project_id}\`);`);
                }
            } else if (results['do_grid_optimization'] === false && results['do_es_design_optimization'] === false) {
                nextButton.setAttribute('onclick', `save_demand_estimation('/export_demand/` + proj_id + '/' + document.getElementById('fileTypeDropdown').value + `/')`);
                nextButton.textContent = 'Export Demand';
            }
            if (results['do_demand_estimation'] === false) {
                document.getElementById("toggleswitch2").checked = true;
                document.getElementById("toggleswitch2").dispatchEvent(new Event('change'));
                }
        } else if (page_name.includes("grid_design")) {
            if (results['do_es_design_optimization'] === false) {
                nextButton.setAttribute('onclick', `save_grid_design(); forward_if_no_task_is_pending(${project_id});`);
                nextButton.textContent = 'Optimize';
            }
        } else if (page_name.includes("energy_system_design")) {
            if (results['do_grid_optimization'] === false) {
                prevButton.setAttribute('onclick', `save_energy_system_design(\`demand_estimation?project_id=${project_id}\`);`);
            }
        }
    }
    updateWizardStepVisibility(results['do_demand_estimation'], results['do_grid_optimization'], results['do_es_design_optimization']);
    wizardSection.classList.add('show');
}


// Function to update the visibility and numbering of wizard steps
function updateWizardStepVisibility(do_demand_estimation, do_grid_optimization, do_energy_system_design) {
    const steps = [
        {element: document.getElementById('wizElement1'), condition: true}, // Always visible
        {element: document.getElementById('wizElement2'), condition: do_demand_estimation || do_grid_optimization},
        {
            element: document.getElementById('wizElement3'),
            condition: do_demand_estimation || do_grid_optimization || do_energy_system_design
        },
        {element: document.getElementById('wizElement4'), condition: do_grid_optimization},
        {element: document.getElementById('wizElement5'), condition: do_energy_system_design},
        {element: document.getElementById('wizElement6'), condition: do_grid_optimization || do_energy_system_design}
    ];

    let visibleStepCount = 1;

    steps.forEach((step, index) => {
        if (step.condition) {
            step.element.style.display = '';
            step.element.setAttribute('data-step-number', visibleStepCount);
            visibleStepCount++;
        } else {
            step.element.style.display = 'none';
            step.element.removeAttribute('data-step-number');
        }
    });

    // Update CSS to use data-step-number for numbering
    const style = document.createElement('style');
    style.textContent = `
        .wizard__steps li[data-step-number]::before {
            content: attr(data-step-number) !important;
        }
    `;
    document.head.appendChild(style);
}
