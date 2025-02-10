/*
// Select the element to be observed
const responseMsgElement = document.getElementById('responseMsg');

// Create a new MutationObserver instance
const observer = new MutationObserver(function(mutationsList, observer) {
    for (const mutation of mutationsList) {
        if (mutation.type === 'characterData' || mutation.type === 'childList') {
            // Show the modal when textContent of responseMsg changes
            document.getElementById('msgBox').style.display = 'block';
        }
    }
});

// Define what to observe (changes to the text content of the element)
observer.observe(responseMsgElement, {
    characterData: true,  // Observes changes to the text content
    childList: true,      // Observes addition/removal of child nodes
    subtree: true         // Observes changes within the descendants of the node
});


// Function to handle toggleswitch0 (Demand Estimation)
document.getElementById('id_do_demand_estimation').addEventListener('change', function() {
    if (!this.checked) {
        // Update the text content of the responseMsg element
        document.getElementById('responseMsg').textContent =
            "If you keep the demand estimation option enabled, you can choose later between estimating demand or using a custom demand time series. If the demand estimation function is not used, a corresponding time series must be uploaded later in the 'Demand Estimation' section.";
        // Show the modal
        document.getElementById('msgBox').style.display = 'block';
    }
});

// Function to handle toggleswitch1 (Spatial Grid Optimization)
document.getElementById('id_do_grid_optimization').addEventListener('change', function() {
    if (!this.checked) {
        // Update the text content of the responseMsg element
        document.getElementById('responseMsg').textContent =
            "A demand is required for the design optimization of energy converters. Demand estimation requires information about consumers, which is defined in the 'Consumer Selection' section using the integrated mapping system. Therefore, even if grid planning is not carried out, consumers must still be specified unless a custom demand time series is uploaded in the 'Demand Estimation' section. In that case, also deactivate 'Demand Estimation' to skip the consumer definition step.";

        // Show the modal
        document.getElementById('msgBox').style.display = 'block';
    }
});
*/
