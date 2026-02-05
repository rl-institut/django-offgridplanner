/**
 * Demand estimation & visualization
 */

/* ================================
   Utilities
================================ */

function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Function to calculate Total_Demand
function calculateTotalDemand(households, enterprises, public_services) {
    return households.map((value, index) => {
        return value + enterprises[index] + public_services[index];
    });
};

function calibrate_demand(reverse = false) {
    var households_raw = AppState.average_shares.map(value => value * AppState.num_households);

    let calibration_factor;
    const total_demand_raw = calculateTotalDemand(households_raw, AppState.enterprises, AppState.public_services);
    if (calibration_option === 'kW') {
        calibration_factor = calibration_target_value / Math.max(...total_demand_raw);
    } else if (calibration_option === 'kWh') {
        calibration_factor = calibration_target_value / total_demand_raw.reduce((a, b) => a + b, 0);
    } else {
        calibration_factor = 1
    }
    households = households_raw.map(value => value * calibration_factor);
    enterprises = AppState.enterprises.map(value => value * calibration_factor);
    public_services = AppState.public_services.map(value => value * calibration_factor);
}

/* ================================
   Global App State
================================ */

const AppState = {
    // needed for plot
    plotReady: false,
    plotElement: null,
    radioTotalDemand: null,
    radioSingleHousehold: null,

    // radio buttons
    toggleSwitch: null, // toggle custom calibration on/off
    option7Radio: null, // total vs peak
    option8Radio: null, // total vs peak
    totalEnergyInput: null,
    maximumPeakLoadInput: null,

    // neended for demand calculations
    customShares: {},
    previousValues: {},
    num_households: 0,
    households: null,
    enterprises: null,
    public_services: null,

    average_raw: [],
    average_shares: [],

    traces: {
        averageIndex: 4, // trace6
        trace1Y: [], //trace1
        trace2Y: [], //trace2
        trace3Y: [], //trace3
        trace4Y: [], //trace4
        trace5Y: [] //trace5
    }
};

/* ================================
   DOM Initialization
================================ */

function initDOM() {
    AppState.plotElement = document.getElementById('demand_plot');
    AppState.radioTotalDemand = document.getElementById('optionTotalDemand');
    AppState.radioSingleHousehold = document.getElementById('optionSingleHousehold');

    AppState.toggleSwitch = document.getElementById('toggleswitch');
    AppState.option7Radio = document.getElementById('option7radio');
    AppState.option8Radio = document.getElementById('option8radio');
    AppState.totalEnergyInput = document.getElementById('id_annual_total_consumption');
    AppState.maximumPeakLoadInput = document.getElementById('id_annual_total_consumption');

    AppState.customShares = {
        id_very_low: document.getElementById('id_very_low'),
        id_low: document.getElementById('id_low'),
        id_middle: document.getElementById('id_middle'),
        id_high: document.getElementById('id_high'),
        id_very_high: document.getElementById('id_very_high')
    };

    Object.entries(AppState.customShares).forEach(([id, el]) => {
        AppState.previousValues[id] = parseFloat(el?.value) || 0;
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initDOM();
    attachInputListeners();
    loadDemandPlot();
});


/* ================================
   Plot Loading
================================ */

function loadDemandPlot() {
    fetch(loadDemandPlotUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            buildPlot(data);
            AppState.plotReady = true;
        })
        .catch(error => {
            console.error('There was a problem with the fetch operation:', error);
        });
}

/* ================================
   Plot Construction
================================ */
const colors = {
    total: 'black',

    households: {
        line: 'rgba(31, 119, 180, 1)',
        fill: 'rgba(31, 119, 180, 0.6)'
    },
    enterprises: {
        line: 'rgba(255, 127, 14, 1)',
        fill: 'rgba(255, 127, 14, 0.6)'
    },
    public_services: {
        line: 'rgba(44, 160, 44, 1)',
        fill: 'rgba(44, 160, 44, 0.6)'
    },

    average: 'black',

    very_high: 'blue',
    high: 'green',
    middle: 'black',
    low: 'orange',
    very_low: 'red'
};

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


function buildPlot(data) {
    const {
        x,
        'Very High Consumption': Very_High,
        'High Consumption': High,
        'Middle Consumption': Middle,
        'Low Consumption': Low,
        'Very Low Consumption': Very_Low,
        Average,
        households,
        enterprises,
        public_services,
        num_households
    } = data.timeseries;

    AppState.average_raw = Average;
    AppState.num_households = num_households;
    AppState.households = households;
    AppState.enterprises = enterprises;
    AppState.public_services = public_services;

    const Total_Demand = calculateTotalDemand(
        households,
        enterprises,
        public_services
    );

    const dataTraces = [
        {
            x: x,
            y: Total_Demand,
            mode: 'lines',
            name: 'Total Demand',
            line: { color: colors.total, width: 3, shape: 'spline' },
            visible: true, // Initially visible
            legendrank: 0
        },
        {
            x: x,
            y: public_services,
            type: 'scatter',
            mode: 'lines',
            name: 'Demand of Public Services',
            stackgroup: 'one',
            fill: 'tonexty',
            hoverinfo: 'x+y',
            line: { shape: 'spline', width: 0.5, color: colors.public_services.line },
            fillcolor: colors.public_services.fill,
            legendrank: 1
        },
        {
            x: x,
            y: enterprises,
            type: 'scatter',
            mode: 'lines',
            name: 'Demand of Enterprises',
            stackgroup: 'one',
            fill: 'tonexty',
            hoverinfo: 'x+y',
            line: { shape: 'spline', width: 0.5, color: colors.enterprises.line },
            fillcolor: colors.enterprises.fill,
            legendrank: 2
        },
        {
            x: x,
            y: households,
            type: 'scatter',
            mode: 'lines',
            name: 'Demand of Households',
            stackgroup: 'one',
            fill: 'tonexty',
            hoverinfo: 'x+y',
            line: { shape: 'spline', width: 0.5, color: colors.households.line },
            fillcolor: colors.households.fill,
            legendrank: 3
        },
        {
            x: x,
            y: Average,
            mode: 'lines',
            name: 'Average Household Profile',
            line: { color: colors.average, width: 2, shape: 'spline' },
            visible: false, // Initially hidden
            legendrank: 4
        },
        {
            x: x,
            y: Very_High,
            mode: 'lines',
            name: 'Very High Consumption',
            line: { color: colors.very_high, width: 1, shape: 'spline' },
            visible: 'legendonly',
            legendrank: 5
        },
        {
            x: x,
            y: High,
            mode: 'lines',
            name: 'High Consumption',
            line: { color: colors.high, width: 1, shape: 'spline' },
            visible: 'legendonly',
            legendrank: 6
        },
        {
            x: x,
            y: Middle,
            mode: 'lines',
            name: 'Middle Consumption',
            line: { color: colors.middle, width: 1, shape: 'spline' },
            visible: 'legendonly',
            legendrank: 7
        },
        {
            x: x,
            y: Low,
            mode: 'lines',
            name: 'Low Consumption',
            line: { color: colors.low, width: 1, shape: 'spline' },
            visible: 'legendonly',
            legendrank: 8
        },
        {
            x: x,
            y: Very_Low,
            mode: 'lines',
            name: 'Very Low Consumption',
            line: { color: colors.very_low, width: 1, shape: 'spline' },
            visible: 'legendonly',
            legendrank: 9
        }
    ];

    //update y-values, so they can be used globally for average share update
    AppState.traces.trace1Y = dataTraces[9].y; // trace1: index 9
    AppState.traces.trace2Y = dataTraces[8].y; // trace2: index 8
    AppState.traces.trace3Y = dataTraces[7].y; // trace3: index 7
    AppState.traces.trace4Y = dataTraces[6].y; // trace4: index 6
    AppState.traces.trace5Y = dataTraces[5].y; // trace5: index 5

    Plotly.react(AppState.plotElement, dataTraces, layout);
}

/* ================================
   Plot Updates
================================ */
// Function to update plot based on selection (total or single household demand)
function showOnlySelection() {
    if (AppState.radioTotalDemand.checked) {
        // Activate traces 1 to 4 (indices 0 to 3)
        Plotly.restyle(AppState.plotElement, { 'visible': true }, [0, 1, 2, 3]);
        // Deactivate traces 5 to 10 (indices 4 to 9)
        Plotly.restyle(AppState.plotElement, { 'visible': 'legendonly' }, [4, 5, 6, 7, 8, 9]);
    } else if (AppState.radioSingleHousehold.checked) {
        // Activate traces 5 to 10 (indices 4 to 9)
        Plotly.restyle(AppState.plotElement, { 'visible': true }, [4, 5, 6, 7, 8, 9]);
        // Deactivate traces 1 to 4 (indices 0 to 3)
        Plotly.restyle(AppState.plotElement, { 'visible': 'legendonly' }, [0, 1, 2, 3]);
    }
}

function updateAverageTrace() {
    if (!AppState.plotReady) return;

    Plotly.restyle(
        AppState.plotElement,{ y: [AppState.average_shares] },[AppState.traces.averageIndex]
    );
}

function updateTrace0to3() {
    Total_Demand = calculateTotalDemand(AppState.households, AppState.enterprises, AppState.public_services);
    // Restyle all traces in one command
    Plotly.restyle(AppState.plotElement, {
        'y': [Total_Demand, AppState.public_services, AppState.enterprises, AppState.households]
    }, [0, 1, 2, 3]);
}

function updateAverageArray() {
    const shares = AppState.customShares;

    //retrieve input values from AppState and convert percentage to decimals
    const share1 = (parseFloat(shares.id_very_low.value) || 0) / 100;
    const share2 = (parseFloat(shares.id_low.value) || 0) / 100;
    const share3 = (parseFloat(shares.id_middle.value) || 0) / 100;
    const share4 = (parseFloat(shares.id_high.value) || 0) / 100;
    const share5 = (parseFloat(shares.id_very_high.value) || 0) / 100;

    AppState.average_raw.forEach((val, idx) => {
        AppState.average_raw[idx] = (share1 * AppState.traces.trace1Y[idx]) +
                                    (share2 * AppState.traces.trace2Y[idx]) +
                                    (share3 * AppState.traces.trace3Y[idx]) +
                                    (share4 * AppState.traces.trace4Y[idx]) +
                                    (share5 * AppState.traces.trace5Y[idx]);
    0});
    AppState.average_shares = AppState.average_raw;
}

/* ================================
   Input Handling
================================ */
// function to handle the input of custom household shares
function handleInputChange(inputId) {
    return function () {
        if (!AppState.plotReady) return;

        const input = AppState.customShares[inputId];
        if (!input) return;

        const newValue = Number(input.value) || 0;
        const oldValue = AppState.previousValues[inputId];

        AppState.previousValues[inputId] = newValue;

        updateAverageArray();
        updateAverageTrace();
        //calibrate_demand();
        updateTrace0to3();
    };
}

// Handle change of calibration values (total vs. peak)
// not sure if this is used on old code or the other way
function handleOptions2Change() {
    if (AppState.option7Radio.checked) {
        AppState.totalEnergyInput.disabled = false;
        AppState.maximumPeakLoadInput.disabled = true;
        AppState.maximumPeakLoadInput.value = '';
    } else {
        AppState.totalEnergyInput.disabled = true;
        AppState.totalEnergyInput.value = '';
        AppState.maximumPeakLoadInput.disabled = false;
    }
}
// Function to handle calibration input changes
function handleCalibrationInputChange() {
    // Only proceed if the toggle switch is activated
    if (AppState.toggleSwitch.checked) {
        if (AppState.option7Radio.checked) {
            // Option 7: "Set Average Total Annual Energy (kWh/year)"
            const value = parseFloat(AppState.totalEnergyInput.value);
            if (!isNaN(value) && value >= 0) {
                calibrate_demand(true);
                calibration_target_value = value;
                calibration_option = 'kWh';
                calibrate_demand(false);
                updateTrace0to3();
            }
        } else if (AppState.option8Radio.checked) {
            // Option 8: "Set Maximum Peak Demand (kW)"
            const value = parseFloat(AppState.maximumPeakLoadInput.value);
            if (!isNaN(value) && value >= 0) {
                calibrate_demand(true);
                calibration_target_value = value;
                calibration_option = 'kW';
                calibrate_demand(false);
                updateTrace0to3();
            }
        }
    } else {
        // Toggle is deactivated
        calibrate_demand(true);
        calibration_target_value = 1;
        calibration_option = null;
        updateTrace0to3();
        households = AppState.average_shares.map(value => value * AppState.num_households);
        calibrate_demand(false);
    }
}

function handleRadioButtonChange() {
    if (AppState.option7Radio.checked) {
        AppState.totalEnergyInput.disabled = false;
        AppState.maximumPeakLoadInput.disabled = true;
        AppState.maximumPeakLoadInput.value = '';
        handleCalibrationInputChange();
    } else if (AppState.option8Radio.checked) {
        AppState.totalEnergyInput.disabled = true;
        AppState.totalEnergyInput.value = '';
        AppState.maximumPeakLoadInput.disabled = false;
        handleCalibrationInputChange();
    }
}

// Adding all the Event Listeners
function attachInputListeners() {
    Object.keys(AppState.customShares).forEach(id => {
        AppState.customShares[id].addEventListener(
            'input',
            handleInputChange(id)
        );
    });
    AppState.radioTotalDemand.addEventListener('change', showOnlySelection);
    AppState.radioSingleHousehold.addEventListener('change', showOnlySelection);
    // custom calibration buttons/switches
    AppState.toggleSwitch.addEventListener('change', function(event) {
        if (!event.target.checked) {
            // Toggle is deactivated
            calibration_target_value = 1;
            calibration_option = null;
            updateTrace0to3();
        }
    });
    AppState.option7Radio.addEventListener('change', handleRadioButtonChange, 1, false);
    AppState.option8Radio.addEventListener('change', handleRadioButtonChange, 1, false);
    AppState.totalEnergyInput.addEventListener('input', debounce(handleCalibrationInputChange, 1000, false));
    AppState.maximumPeakLoadInput.addEventListener('input', debounce(handleCalibrationInputChange, 1000, false));
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


/* ================================
   Reset Custom Share Input
================================ */

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

/* ================================
   File Handling
================================ */

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
