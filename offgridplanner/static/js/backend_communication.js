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

let hasRetried = false;

async function load_results(project_id) {
    await db_nodes_to_js(markers_only=false);
    await plot_results();
    await db_roads_to_js(proj_id);
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
