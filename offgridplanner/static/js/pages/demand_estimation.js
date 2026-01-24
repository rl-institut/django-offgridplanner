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

function isSignificantChange(newValue, oldValue, threshold = 0.2) {
    return Math.abs(newValue - oldValue) >= threshold;
}

// Function to calculate Total_Demand
function calculateTotalDemand(households, enterprises, public_services) {
    return households.map((value, index) => {
        return value + enterprises[index] + public_services[index];
    });
};

function calibrate_demand(reverse = false) {
    var households_raw = Average.map(value => value * AppState.num_households);

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

/* ================================
   Global App State
================================ */

const AppState = {
    plotReady: false,
    plotElement: null,

    customShares: {},
    previousValues: {},
    num_households: 0,
    households: null,
    enterprises: null,
    public_services: null,


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

    window.Average = Average; // required by updateTrace6()
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
            x, y: Total_Demand, mode: 'lines',
            name: 'Total Demand',
            line: { width: 3, shape: 'spline' },
            legendrank: 0
        },
        {
            x, y: public_services, stackgroup: 'one',
            name: 'Demand of Public Services',
            fill: 'tonexty', legendrank: 1
        },
        {
            x, y: enterprises, stackgroup: 'one',
            name: 'Demand of Enterprises',
            fill: 'tonexty', legendrank: 2
        },
        {
            x, y: households, stackgroup: 'one',
            name: 'Demand of Households',
            fill: 'tonexty', legendrank: 3
        },
        {
            x, y: Average,
            name: 'Average Household Profile',
            visible: false,
            legendrank: 4
        },
        { x, y: Very_High, name: 'Very High Consumption', visible: 'legendonly' },
        { x, y: High, name: 'High Consumption', visible: 'legendonly' },
        { x, y: Middle, name: 'Middle Consumption', visible: 'legendonly' },
        { x, y: Low, name: 'Low Consumption', visible: 'legendonly' },
        { x, y: Very_Low, name: 'Very Low Consumption', visible: 'legendonly' }
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

function updateTrace6() {
    if (!AppState.plotReady) return;

    Plotly.restyle(
        AppState.plotElement,
        { y: [Average] },
        [AppState.traces.averageIndex]
    );
}

function updateTrace7to10() {
    Total_Demand = calculateTotalDemand(AppState.households, AppState.enterprises, AppState.public_services);
    // Restyle all traces in one command
    Plotly.restyle(AppState.plotElement, {
        'y': [Total_Demand, AppState.public_services, AppState.enterprises, AppState.households]
    }, [0, 1, 2, 3]);
}

function updateAverageArray() {
    const shares = AppState.customShares;

    //retrieve input values from AppState and convert percantage to decimals
    const share1 = (parseFloat(shares.id_very_low.value) || 0) / 100;
    const share2 = (parseFloat(shares.id_low.value) || 0) / 100;
    const share3 = (parseFloat(shares.id_middle.value) || 0) / 100;
    const share4 = (parseFloat(shares.id_high.value) || 0) / 100;
    const share5 = (parseFloat(shares.id_very_high.value) || 0) / 100;

    Average.forEach((val, idx) => {
        Average[idx] = (share1 * AppState.traces.trace1Y[idx]) +
                        (share2 * AppState.traces.trace2Y[idx]) +
                        (share3 * AppState.traces.trace3Y[idx]) +
                        (share4 * AppState.traces.trace4Y[idx]) +
                        (share5 * AppState.traces.trace5Y[idx]);
    0});
}

/* ================================
   Input Handling
================================ */

function handleInputChange(inputId) {
    return function () {
        if (!AppState.plotReady) return;

        const input = AppState.customShares[inputId];
        if (!input) return;

        const newValue = Number(input.value) || 0;
        const oldValue = AppState.previousValues[inputId];

        if (!isSignificantChange(newValue, oldValue)) return;

        AppState.previousValues[inputId] = newValue;

        updateAverageArray();
        updateTrace6();
        //calibrate_demand();
        updateTrace7to10();
    };
}

function attachInputListeners() {
    Object.keys(AppState.customShares).forEach(id => {
        AppState.customShares[id].addEventListener(
            'input',
            handleInputChange(id)
        );
    });
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
