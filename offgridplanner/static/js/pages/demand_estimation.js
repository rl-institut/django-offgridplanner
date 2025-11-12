/**
 * This script handles UI interactions and data visualization in a web application.
 * - Toggles visibility of an accordion section based on a switch.
 * - Adjusts input fields in response to radio button selections.
 * - Listens for radio button changes and stores the selected value.
 * - Fetches and plots time series data for demand profiles using Plotly.
 */


function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

// Store selected value from radio buttons with name 'options'
const radioButtons = document.getElementsByName("options");
const option7Container = document.getElementById("option7");
const option8Container = document.getElementById("option8");
const option7Radio = document.getElementById('option7radio');
const option8Radio = document.getElementById('option8radio');
const totalEnergyInput = document.getElementById('id_annual_total_consumption');
const maximumPeakLoadInput = document.getElementById('id_annual_peak_consumption');
const toggleSwitch = document.getElementById('toggleswitch');
// Get references to the radio buttons
const radioTotalDemand = document.getElementById('optionTotalDemand');
const radioSingleHousehold = document.getElementById('optionSingleHousehold');
const plotElement = document.getElementById("demand_plot");


// Adjust input fields based on radio button selection
document.addEventListener('DOMContentLoaded', function () {
    const proj_id = "{{ proj_id }}";
    demand_ts(proj_id)

document.querySelectorAll(".btn-custom").forEach((btn) => {
    btn.addEventListener("click", function (event) {
        // Prevent the event from affecting the form field inputs
        if (!event.target.classList.contains("form-control")) {
            console.log("alsjda")
            const radioInput = btn.querySelector("input[type='radio']");
            if (radioInput) {
                console.log("slkdjf")
                radioInput.checked = true;
            }
            handleOptions2Change();
        }
    });
});

    // Initial setup
    handleOptions2Change();

});

// Handle change of calibration values (total vs. peak)
function handleOptions2Change() {
    if (option7Radio.checked) {
        totalEnergyInput.disabled = false;
        maximumPeakLoadInput.disabled = true;
        maximumPeakLoadInput.value = '';
    } else {
        totalEnergyInput.disabled = true;
        totalEnergyInput.value = '';
        maximumPeakLoadInput.disabled = false;
    }
}

// TODO the automatic calibration is not working yet
// Function to calculate Total_Demand
function calculateTotalDemand(households, enterprises, public_services) {
    return households.map((value, index) => {
        return value + enterprises[index] + public_services[index];
    });
}

// Updates trace6 (Single Household Profile) based on custom share inputs
function updateTrace6() {
    // Update trace6's Y-values in the Plotly plot
    Plotly.restyle(plotElement, { 'y': [Average] }, [4]); // trace6 is at index 4
}

// TODO this is so the trace only updates if the value raises by > threshold
// Function to check if the change is significant (≥ 0.5)
function isSignificantChange(newValue, oldValue, threshold = 0.2) {
    return Math.abs(newValue - oldValue) >= threshold;
}

// Function to handle input changes with threshold
function handleInputChange(inputId) {
    return function () {
        const input = document.getElementById(inputId);
        const newValue = parseFloat(input.value) || 0;
        const oldValue = previousValues[inputId];
        if (isSignificantChange(newValue, oldValue)) {
            previousValues[inputId] = newValue;
            updateAverageArray()
            updateTrace6();
            calibrate_demand();
            updateTrace7to10();
        }
    };
}

// Function to update plot based on selection
function showOnlySelection() {
    if (radioTotalDemand.checked) {
        // Activate traces 1 to 4 (indices 0 to 3)
        Plotly.restyle(plotElement, { 'visible': true }, [0, 1, 2, 3]);
        // Deactivate traces 5 to 10 (indices 4 to 9)
        Plotly.restyle(plotElement, { 'visible': 'legendonly' }, [4, 5, 6, 7, 8, 9]);
    } else if (radioSingleHousehold.checked) {
        // Activate traces 5 to 10 (indices 4 to 9)
        Plotly.restyle(plotElement, { 'visible': true }, [4, 5, 6, 7, 8, 9]);
        // Deactivate traces 1 to 4 (indices 0 to 3)
        Plotly.restyle(plotElement, { 'visible': 'legendonly' }, [0, 1, 2, 3]);
    }
}

function calibrate_demand(reverse = false) {
    var households_raw = Average.map(value => value * num_households);

    let calibration_factor;
    const total_demand_raw = calculateTotalDemand(households_raw, enterprises_raw, public_services_raw);
    if (calibration_option === 'kW') {
        calibration_factor = calibration_target_value / Math.max(...total_demand_raw);
    } else if (calibration_option === 'kWh') {
        calibration_factor = calibration_target_value / total_demand_raw.reduce((a, b) => a + b, 0);
    } else {
        calibration_factor = 1
    }
    households = households_raw.map(value => value * calibration_factor);
    enterprises = enterprises_raw.map(value => value * calibration_factor);
    public_services = public_services_raw.map(value => value * calibration_factor);
}

function updateTrace7to10() {
    Total_Demand = calculateTotalDemand(households, enterprises, public_services);
    // Restyle all traces in one command
    Plotly.restyle(plotElement, {
        'y': [Total_Demand, public_services, enterprises, households]
    }, [0, 1, 2, 3]);
}

function updateAverageArray() {
    // Retrieve and parse input values, converting percentages to decimals
    const share1 = parseFloat(customShare1.value) / 100 || 0;
    const share2 = parseFloat(customShare2.value) / 100 || 0;
    const share3 = parseFloat(customShare3.value) / 100 || 0;
    const share4 = parseFloat(customShare4.value) / 100 || 0;
    const share5 = parseFloat(customShare5.value) / 100 || 0;

    Average.forEach((val, idx) => {
        Average[idx] = (share1 * trace1Y[idx]) +
                        (share2 * trace2Y[idx]) +
                        (share3 * trace3Y[idx]) +
                        (share4 * trace4Y[idx]) +
                        (share5 * trace5Y[idx]);
    0});
}

function resetToDefault() {
    // Recalculate 'Average' using default shares
    updateAverageArray();

    // Update trace6 (Single Household Profile)
    updateTrace6();

    // Reset calibration settings
    calibration_target_value = 1;
    calibration_option = null;

    // Recalculate 'households' based on new 'Average' and 'num_households'
    households = Average.map(value => value * num_households);

    // Reset 'enterprises' and 'public_services' to their raw values
    enterprises = enterprises_raw.slice(); // Make a copy to avoid modifying the original array
    public_services = public_services_raw.slice(); // Make a copy

    // Recalculate 'Total_Demand'
    Total_Demand = calculateTotalDemand(households, enterprises, public_services);

    // Update the plot for traces 0 to 3 (Total Demand, public services, enterprises, households)
    Plotly.restyle(plotElement, {
        'y': [Total_Demand, public_services, enterprises, households]
    }, [0, 1, 2, 3]);
}

// Function to handle calibration input changes
function handleCalibrationInputChange() {
    // Only proceed if the toggle switch is activated
    if (toggleSwitch.checked) {
        if (option7Radio.checked) {
            // Option 7: "Set Average Total Annual Energy (kWh/year)"
            const value = parseFloat(totalEnergyInput.value);
            if (!isNaN(value) && value >= 0) {
                calibrate_demand(true);
                calibration_target_value = value;
                calibration_option = 'kWh';
                calibrate_demand(false);
                updateTrace7to10();
            }
        } else if (option8Radio.checked) {
            // Option 8: "Set Maximum Peak Demand (kW)"
            const value = parseFloat(maximumPeakLoadInput.value);
            if (!isNaN(value) && value >= 0) {
                calibrate_demand(true);
                calibration_target_value = value;
                calibration_option = 'kW';
                calibrate_demand(false);
                updateTrace7to10();
            }
        }
    } else {
        // Toggle is deactivated
        calibrate_demand(true);
        calibration_target_value = 1;
        calibration_option = null;
        updateTrace7to10();
        households = Average.map(value => value * num_households);
        calibrate_demand(false);
    }
}

// Add event listeners to the radio buttons for calibration options
function handleRadioButtonChange() {
    if (option7Radio.checked) {
        totalEnergyInput.disabled = false;
        maximumPeakLoadInput.disabled = true;
        maximumPeakLoadInput.value = '';
        handleCalibrationInputChange();
    } else if (option8Radio.checked) {
        totalEnergyInput.disabled = true;
        totalEnergyInput.value = '';
        maximumPeakLoadInput.disabled = false;
        handleCalibrationInputChange();
    }
}


function demand_ts(project_id) {

    var layout = {
        font: { size: 14 },
        autosize: true,
        xaxis: {
            title: 'Hour of the day',
            hoverformat: '.1f',
            titlefont: { size: 16 },
            tickfont: { size: 14 },
        },
        yaxis: {
            title: 'Demand (kW)',
            hoverformat: '.1f',
            titlefont: { size: 16 },
            tickfont: { size: 14 },
        },
        legend: {
            orientation: 'h',
            x: 0,
            y: -0.3,
            xanchor: 'left',
            yanchor: 'top',
            traceorder: 'normal' // Ensure legendrank is honored
        }
    };

    // Initialize the plot with empty data
    Plotly.newPlot(plotElement, [], layout);

    fetch(loadDemandPlotUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Extract data
            // TODO all that is needed to plot the demand should be households, enterprises and public ts from view
            // TODO recalculate those values when calibration values are changed - this still needs to happen in js
            let {
                'x': x,
                'Very High Consumption': Very_High,
                'High Consumption': High,
                'Middle Consumption': Middle,
                'Low Consumption': Low,
                'Very Low Consumption': Very_Low,
                'Average': Average,
                'households': households,
                'enterprises': enterprises,
                'public_services': public_services,
            } = data.timeseries;

//            const enterprises_raw = enterprises.map(value => value / calibration_factor);
//            const public_services_raw = public_services.map(value => value / calibration_factor);


            // Usage inside your main function or logic
            var Total_Demand = calculateTotalDemand(households, enterprises, public_services);

            // Define traces
            var trace10 = {
                x: x,
                y: Total_Demand,
                mode: 'lines',
                name: 'Total Demand',
                line: { color: 'black', width: 3, shape: 'spline' },
                visible: true, // Initially visible
                legendrank: 0
            };

            var trace7 = {
                x: x,
                y: households,
                type: 'scatter',
                mode: 'lines',
                name: 'Demand of Households',
                stackgroup: 'one',
                fill: 'tonexty',
                hoverinfo: 'x+y',
                line: { shape: 'spline', width: 0.5, color: 'rgba(31, 119, 180, 1)' },
                fillcolor: 'rgba(31, 119, 180, 0.6)',
                legendrank: 3
            };

            var trace8 = {
                x: x,
                y: enterprises,
                type: 'scatter',
                mode: 'lines',
                name: 'Demand of Enterprises',
                stackgroup: 'one',
                fill: 'tonexty',
                hoverinfo: 'x+y',
                line: { shape: 'spline', width: 0.5, color: 'rgba(255, 127, 14, 1)' },
                fillcolor: 'rgba(255, 127, 14, 0.6)',
                legendrank: 2
            };

            var trace9 = {
                x: x,
                y: public_services,
                type: 'scatter',
                mode: 'lines',
                name: 'Demand of Public Services',
                stackgroup: 'one',
                fill: 'tonexty',
                hoverinfo: 'x+y',
                line: { shape: 'spline', width: 0.5, color: 'rgba(44, 160, 44, 1)' },
                fillcolor: 'rgba(44, 160, 44, 0.6)',
                legendrank: 1
            };

            var trace6 = {
                x: x,
                y: Average,
                mode: 'lines',
                name: 'Average Household Profile',
                line: { color: 'black', width: 2, shape: 'spline' },
                visible: false, // Initially hidden
                legendrank: 4
            };

            var trace5 = {
                x: x,
                y: Very_High,
                mode: 'lines',
                name: 'Very High Consumption',
                line: { color: 'blue', width: 1, shape: 'spline' },
                visible: 'legendonly',
                legendrank: 5
            };

            var trace4 = {
                x: x,
                y: High,
                mode: 'lines',
                name: 'High Consumption',
                line: { color: 'green', width: 1, shape: 'spline' },
                visible: 'legendonly',
                legendrank: 6
            };

            var trace3 = {
                x: x,
                y: Middle,
                mode: 'lines',
                name: 'Middle Consumption',
                line: { color: 'black', width: 1, shape: 'spline' },
                visible: 'legendonly',
                legendrank: 7
            };

            var trace2 = {
                x: x,
                y: Low,
                mode: 'lines',
                name: 'Low Consumption',
                line: { color: 'orange', width: 1, shape: 'spline' },
                visible: 'legendonly',
                legendrank: 8
            };

            var trace1 = {
                x: x,
                y: Very_Low,
                mode: 'lines',
                name: 'Very Low Consumption',
                line: { color: 'red', width: 1, shape: 'spline' },
                visible: 'legendonly',
                legendrank: 9
            };

            // Data array (order is important for stacking and layering)
            var dataTraces = [trace10, trace9, trace8, trace7, trace6, trace5, trace4, trace3, trace2, trace1];

            // Render plot with all traces
            Plotly.react(plotElement, dataTraces, layout);

            // Store trace1 to trace5 Y-values
            const trace1Y = dataTraces[9].y; // trace1: index 9
            const trace2Y = dataTraces[8].y; // trace2: index 8
            const trace3Y = dataTraces[7].y; // trace3: index 7
            const trace4Y = dataTraces[6].y; // trace4: index 6
            const trace5Y = dataTraces[5].y; // trace5: index 5

            // Get references to custom_share input fields
            const customShare1 = document.getElementById('id_very_low');
            const customShare2 = document.getElementById('id_low');
            const customShare3 = document.getElementById('id_middle');
            const customShare4 = document.getElementById('id_high');
            const customShare5 = document.getElementById('id_very_high');

            // Initialize an object to store previous values of custom share inputs
            const previousValues = {
                'id_very_low': parseFloat(customShare1.value) || 0,
                'id_low': parseFloat(customShare2.value) || 0,
                'id_middle': parseFloat(customShare3.value) || 0,
                'id_high': parseFloat(customShare4.value) || 0,
                'id_very_high': parseFloat(customShare5.value) || 0
            };

            // Attach event listener to reset button
            document.getElementById('resetDefault').addEventListener('click', resetToDefault);

            // Add event listeners with threshold logic
            customShare1.addEventListener('input', handleInputChange('id_very_low'), 250, false);
            customShare2.addEventListener('input', handleInputChange('id_low'), 250, false);
            customShare3.addEventListener('input', handleInputChange('id_middle'), 250, false);
            customShare4.addEventListener('input', handleInputChange('id_high'), 250, false);
            customShare5.addEventListener('input', handleInputChange('id_very_high'), 250, false);

            // Add event listeners to radio buttons
            radioTotalDemand.addEventListener('change', showOnlySelection);
            radioSingleHousehold.addEventListener('change', showOnlySelection);

            // Add event listener to the toggle switch
            toggleSwitch.addEventListener('change', function(event) {
                if (!event.target.checked) {
                    // Toggle is deactivated
                    calibration_target_value = 1;
                    calibration_option = null;
                    updateTrace7to10();
                }
            });

            option7Radio.addEventListener('change', handleRadioButtonChange, 1, false);
            option8Radio.addEventListener('change', handleRadioButtonChange, 1, false);

            // Add event listeners to the calibration input fields with debounce
            totalEnergyInput.addEventListener('input', debounce(handleCalibrationInputChange, 1000, false));
            maximumPeakLoadInput.addEventListener('input', debounce(handleCalibrationInputChange, 1000, false));

        })
        .catch(error => {
            console.error('There was a problem with the fetch operation:', error);
        });
}

// Trigger the file input dialog when the "Import Consumers" button is clicked
document.getElementById('importButton').addEventListener('click', function() {
    document.getElementById('fileInput').click();
});

// Handle the file selection and upload the file to the server
document.getElementById('fileInput').addEventListener('change', async function(event) {
    const file = event.target.files[0];
    if (file) {
        const formData = new FormData();
        formData.append('file', file);
        await file_demand_to_db(formData);
        document.getElementById('fileInput').value = '';
    }
});


function loadDashboard() {
    const dashboardSection = document.querySelector('.dashboard');

    // Check if the 'loading' class is not already present
    if (!dashboardSection.classList.contains('loading')) {
        dashboardSection.classList.add('loading');
    }
}


async function export_demand(file_type) {
    const response = await fetch(exportDemandUrl, {
        method: "POST",
        headers: {"Content-Type": "application/json", 'X-CSRFToken': csrfToken},
        body: JSON.stringify({"file_type": file_type})
    });

    if (response.ok) {
        // Handle the file download for "csv" or "xlsx"
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = file_type === "xlsx" ? "offgridplanner_demand.xlsx" : "offgridplanner_demand.csv";
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(downloadUrl);
    } else {
        console.error('Request failed with status:', response.status);
        const errorDetails = await response.json();
        console.error('Error details:', errorDetails);
    }
}

// update UI element to show users that they need to enter input of total 100%
function updateDemandCheck() {
    const inputs = document.querySelectorAll(".shares-container input[type='number']");
    let sum = 0;
    inputs.forEach(input => {
        sum += parseFloat(input.value) || 0;
    });
    // fix floating point precision with 2 decimals precision
    sum = Math.round(sum * 100) / 100;

    const display = document.getElementById("demand-check");
    display.innerText = sum.toFixed(2) + "%";

    display.classList.remove("shares_correct", "shares_incorrect");

    // Apply color
    if (sum === 100) {
        display.classList.add("shares_correct");
    } else {
        display.classList.add("shares_incorrect");
    }
}
// household demand shares should be checked on first load and every input change
document.addEventListener("DOMContentLoaded", updateDemandCheck);
document.addEventListener("input", updateDemandCheck);

// add functionality to reset Shares Button
document.getElementById("resetShares").addEventListener("click", () => {
    const inputs = document.querySelectorAll(".shares-container input[type='number']");

    inputs.forEach(input => {
        input.value = ""; // or input.defaultValue if Django pre-fills data
    });

    if (typeof updateDemandCheck === "function") {
        updateDemandCheck();
    }
});
