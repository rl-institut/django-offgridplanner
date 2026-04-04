/**
 * This script manages map interactions in a web application, focusing on consumer types and specific services or
 * enterprises.
 * - Dynamically populates dropdown menus based on consumer types ('Household', 'Enterprise', 'Public Service').
 * - Includes separate lists for 'Enterprise' and 'Public Service', each with specific categories, used to update
 *   dropdowns based on consumer choice.
 * - Manages a list of large electrical loads and updates the UI to display these options based on the selected
 *   enterprise or service.
 * - Implements functions to handle map marker interactions, such as adding new consumers, updating existing ones, and
 *   custom icon management.
 * - Uses MutationObserver to monitor UI changes and display modals for user alerts.
 * - Includes utility functions for updating UI elements and handling user inputs related to the map and consumer
 *   details.
 * - Designed to support dynamic interaction and visualization of spatial data for planning or resource allocation in
 *   a geographical mapping context.
 */


let consumer_list = {
    'H': 'Household',
    'E': 'Enterprise',
    'P': 'Public Service',
};
let consumer_type = "H";

(function () {
    let option_consumer = '';
    for (let consumer_code in consumer_list) {
        let selected = (consumer_code == consumer_type) ? ' selected' : '';
        option_consumer += '<option value="' + consumer_code + '"' + selected + '>' + consumer_list[consumer_code] + '</option>';
    }
    document.getElementById('consumer').innerHTML = option_consumer;
})();


// let enterprise_option = '';

function dropDownMenu(dropdown_list, selectedValue = undefined) {
    /*  creates a string that contains the list of options depending on dropdown_list
        selectedValue = undefined, if nothing was selected previously, than first entry will be selected
        selectedValue = null, if multiple markers were selected and their values dont match
    */

    let enterprise_option = '';

    if (selectedValue === null) {
        enterprise_option += '<option value="" selected></option>';
    }

    let isFirstIteration = true;
    for (let enterprise_code in dropdown_list) {
        let selected = '';
        if (isFirstIteration && selectedValue === undefined) {
            selected = ' selected';
        } else if (enterprise_code == selectedValue) {
            selected = ' selected';
        }
        enterprise_option += '<option value="' + enterprise_code + '"' + selected + '>'
            + dropdown_list[enterprise_code] +
            '</option>';
        isFirstIteration = false;
    }

    const enterpriseDropdown = document.getElementById('enterprise');
    enterpriseDropdown.innerHTML = enterprise_option;
    enterpriseDropdown.disabled = false;
}

let large_load_type = "group1";

let option_load = '';
for (let load_code in large_load_list) {
    let selected = (load_code == large_load_type) ? ' selected' : '';
    option_load += '<option value="' + load_code + '"' + selected + '>' + large_load_list[load_code] + '</option>';
}
document.getElementById('loads').innerHTML = option_load;


document.getElementById('loads').disabled = true;
document.getElementById('loads').value = "";
document.getElementById('number_loads').disabled = true;

// Add EventListener to consumer_type dropdwon Menu
document.getElementById('consumer').addEventListener('change', function () {
    let newType;

    if (this.value === 'H') {
        newType = "household";
        document.getElementById('enterprise').value = '';
        document.getElementById('enterprise').disabled = true;
        deactivate_large_loads();

    } else if (this.value === 'E') {
        newType = "enterprise";
        dropDownMenu(enterprise_list);
        document.getElementById('enterprise').disabled = false;
        activate_large_loads();

    } else if (this.value === 'P') {
        newType = "public_service";
        dropDownMenu(public_service_list);
        deactivate_large_loads();
    }

    // edit multiple markers at the same time if shift click was used
    selectedMarkers.forEach(marker => {
        marker.consumer_type = newType;
    });

    count_consumers();
});

// set up the inital state of dropdowns
document.getElementById('enterprise').disabled = true;
document.getElementById('consumer').disabled = true;
document.getElementById('enterprise').value = '';
document.getElementById('consumer').value = '';
document.getElementById('shs_options').disabled = true;
document.getElementById('shs_options').value = '';

document.getElementById('enterprise').addEventListener('change', function () {
    update_map_elements();
});
document.getElementById('shs_options').addEventListener('change', function () {
    update_map_elements();
});


let markerConsumerSelected = new L.Icon({
    iconUrl: "/static/assets/icons/i_consumer_selected.svg",
    iconSize: [12, 12],
});

let markerPowerHouseSelected = new L.Icon({
    iconUrl: "/static/assets/icons/i_power_house_selected.svg",
    iconSize: [12, 12],
});


function getKeyByValue(object, value) {
    return Object.keys(object).find(key => object[key] === value);
}


let selectedMarkers = [];
let clickedMarker;

function markerOnClick(e) {
    // is called with every click on a marker, distinguishes between normal = single-click and shift+click = multi-select
    L.DomEvent.stopPropagation(e);
    const isShift = e.originalEvent.shiftKey;
    if (!isShift) {
        //reset if "normal" click without shift
        if (selectedMarkers.length > 0) {
            selectedMarkers.forEach(marker => {
                resetMarkerIcon(marker);
            });
        }
        selectedMarkers = [];
        oldMarkers = [];
        document.getElementById('longitude').disabled = false;
        document.getElementById('latitude').disabled = false;
        // vlt rausnehmen? passiert am ende eh nochmal in jedem fall
        updateConsumerDropdownForSelection();
    }
    expandAccordionItem2();

    // unselect marker if it was already selected before
    const selectedIndex = selectedMarkers.findIndex(
        m => m.latitude === e.latlng.lat && m.longitude === e.latlng.lng
    );
    if (isShift && selectedIndex !== -1) {
        const removedMarker = selectedMarkers.splice(selectedIndex, 1)[0];
        resetMarkerIcon(removedMarker);
        map_elements.push(removedMarker);
        updateConsumerDropdownForSelection();
        return;
    }

    const index = map_elements.findIndex(obj => obj.latitude === e.latlng.lat && obj.longitude === e.latlng.lng);
    if (index >= 0) {
        clickedMarker = map_elements.splice(index, 1)[0];
        clickedMarker._oldLat = clickedMarker.latitude;
        clickedMarker._oldLng = clickedMarker.longitude;

        selectedMarkers.push(clickedMarker);
        if (selectedMarkers.length > 1) {
            document.getElementById('longitude').disabled = true;
            document.getElementById('latitude').disabled = true;
        }
    }
    map.eachLayer(function (layer) {
        if (layer instanceof L.Marker) {
            let markerLatLng = layer.getLatLng();
            if (markerLatLng.lat === e.latlng.lat && markerLatLng.lng === e.latlng.lng) {
                map.removeLayer(layer);
                let markerIcon;
                if (clickedMarker.node_type === 'power-house') {
                    markerIcon = markerPowerHouseSelected;
                } else {
                    markerIcon = markerConsumerSelected;
                }
                L.marker([markerLatLng.lat, markerLatLng.lng], {icon: markerIcon,})
                    .on('click', markerOnClick).addTo(map);
                document.getElementById('longitude').value = clickedMarker.longitude;
                document.getElementById('latitude').value = clickedMarker.latitude;
                if (clickedMarker.node_type === 'power-house') {
                    document.getElementById('consumer').disabled = true;
                    document.getElementById('shs_options').value = '';
                    document.getElementById('shs_options').disabled = true;
                    document.getElementById('enterprise').disabled = true;
                } else if (clickedMarker.consumer_type === 'household') {
                    document.getElementById('enterprise').disabled = true;
                    document.getElementById('shs_options').disabled = false;
                    document.getElementById('consumer').disabled = false;
                } else if (clickedMarker.consumer_type === 'enterprise') {
                    document.getElementById('shs_options').disabled = false;
                    document.getElementById('consumer').disabled = false;
                } else if (clickedMarker.consumer_type === 'public_service') {
                    document.getElementById('shs_options').disabled = false;
                    document.getElementById('consumer').disabled = false;
                }
            }
        }
    });
    // handle large loads section for selected markers
    if (clickedMarker.consumer_type === 'enterprise') {
        activate_large_loads(true);
        const commonLoads = getCommonLoads(selectedMarkers);
        commonLoads.forEach(load => {
            fillList(load);
        });
        if (clickedMarker.custom_specification.length > 5) {
            activate_large_loads(false);
            document.getElementById('toggleswitch2').checked = true;
            const accordionItem3 = new bootstrap.Collapse(document.getElementById('collapseThree'), {
                toggle: false
            });
            accordionItem3.show();
        }
    } else {
        deactivate_large_loads();
    }
    // handle updating the input options for the dropdowns depending on consumer type
    updateConsumerDropdownForSelection();
}

function update_map_elements() {
    // updates map elements based on chosen values and also saves chosen values to marker nodes
    const isMultiSelect = selectedMarkers.length > 1;
    let longitude = document.getElementById('longitude').value;
    let latitude = document.getElementById('latitude').value;
    let shs_options = document.getElementById('shs_options').value;
    let shs_value;
    let large_load_string = large_loads_to_string();

    // kann das hier evt raus, weil das ja gewisse multi select sachen überschreiben würde?
    switch (shs_options) {
        case 'optimize':
            shs_value = 0;
            break;
        case 'grid':
            shs_value = 1;
            break;
        default:
            shs_value = 0;
    }

    let selected_icon;

    selectedMarkers.forEach((marker, i) => {
        let oldLat = marker._oldLat;
        let oldLng = marker._oldLng;

        if (!isMultiSelect && longitude.length > 0 && latitude.length > 0) {
            marker.longitude = parseFloat(longitude);
            marker.latitude = parseFloat(latitude);
        }
        marker.shs_options = parseInt(shs_value);
        marker.custom_specification = large_load_string;

        let consumerValue = document.getElementById('consumer').value;

        switch (consumerValue) {
            case 'H':
                marker.consumer_type = 'household';
                marker.consumer_detail = '';
                selected_icon = markerConsumer;
                break;
            case 'P':
                marker.consumer_type = 'public_service';
                let key2 = document.getElementById('enterprise').value || 'group1';
                marker._consumer_detail_key = key2;
                marker.consumer_detail = public_service_list[key2];
                selected_icon = markerPublicservice;
                break;
            case 'E':
                marker.consumer_type = 'enterprise';
                let key = document.getElementById('enterprise').value || 'group1';
                marker._consumer_detail_key = key;
                marker.consumer_detail = enterprise_list[key];
                selected_icon = markerEnterprise;
                break;
            case '':
                marker.node_type = 'power-house';
                marker.consumer_type = '';
                marker.consumer_detail = '';
                selected_icon = markerPowerHouse;
                break;
            default:
                console.error("Invalid consumer value: " + consumerValue);
        }

        if (marker.shs_options == 2) {
            selected_icon = markerShs;
        }
        if (!map_elements.includes(marker)) {
            map_elements.push(marker);
        }

        map.eachLayer(function (layer) {
            if (layer instanceof L.Marker) {
                let markerLatLng = layer.getLatLng();
                if (markerLatLng.lat === oldLat && markerLatLng.lng === oldLng) {
                    map.removeLayer(layer);
                    L.marker([marker.latitude, marker.longitude], {icon: selected_icon})
                        .on('click', markerOnClick).addTo(map);
                }
            }
        });
        marker._oldLat = marker.latitude;
        marker._oldLng = marker.longitude;
    });
    count_consumers(false)
}

function resetMarkerIcon(marker) {
    // just resets the marker Icon based marker consumer_type
    const epsilon = 0.0000001;

    map.eachLayer(function(layer) {
        if (layer instanceof L.Marker) {
            let latLng = layer.getLatLng();

            if (Math.abs(latLng.lat - marker.latitude) < epsilon &&
                Math.abs(latLng.lng - marker.longitude) < epsilon) {

                map.removeLayer(layer);

                let normalIcon;

                if (marker.node_type === 'power-house') {
                    normalIcon = markerPowerHouse;
                } else if (marker.consumer_type === 'enterprise') {
                    normalIcon = markerEnterprise;
                } else if (marker.consumer_type === 'public_service') {
                    normalIcon = markerPublicservice;
                } else {
                    normalIcon = markerConsumer;
                }

                L.marker([marker.latitude, marker.longitude], {icon: normalIcon})
                    .on('click', markerOnClick)
                    .addTo(map);

                // important: marker needs to be put back in datastructure since it's being sliced from there
                if (!map_elements.includes(marker)) {
                    map_elements.push(marker);
                }
            }
        }
    });
}

function check_map_elements() {
    // checks all the map elements/markers if they have missing values
    map_elements.forEach((marker, i) => {
        let consumerValue = marker.consumer_type;

        switch (consumerValue) {
            case 'household':
                // put checks for households here
                break;
            case 'public_service':
                // put checks for public services here
                break;
            case 'enterprise':
                const key = getKeyByValue(enterprise_list, marker.consumer_detail);

                if (!key || marker.consumer_detail === 'null' || !marker.consumer_detail) {
                    marker.consumer_detail = enterprise_list['group1'];

                    const indexInMapElements = map_elements.findIndex(
                        m => m.latitude === marker.latitude && m.longitude === marker.longitude
                    );

                    if (indexInMapElements !== -1) {
                        map_elements[indexInMapElements].consumer_detail = marker.consumer_detail;
                        map_elements[indexInMapElements]._consumer_detail_key = 'group1';
                    } else if (!map_elements.includes(marker)) {
                        map_elements.push(marker);
                    }
                }
                break;
            case '':
                // put checks for power houses here
                break;
            default:
                console.error("Invalid consumer value: " + consumerValue);
        }
    });
}

function updateConsumerDropdownForSelection() {
    // function differentiates on multi-consumer selection if all selected consumers have the same type or not
    // if yes, the chosen type is shown as selected, if not the default list is shown

    const consumerDropdown = document.getElementById('consumer');
    const enterpriseDropdown = document.getElementById('enterprise');
    const shsOptionsDropdown = document.getElementById('shs_options');

    if (selectedMarkers.length === 0) {
        consumerDropdown.value = '';
        enterpriseDropdown.innerHTML = '';
        enterpriseDropdown.disabled = true;
        return;
    }

    // handle comparison and differences of consumer types

    const firstType = selectedMarkers[0].consumer_type;
    const allSameType = selectedMarkers.every(m =>
        m.consumer_type === firstType
    );

    if (!allSameType) {
        // consumer_type doesn't match between all the selectedMarkes -> default #consumer dropdown is shown (empty)
        consumerDropdown.value = '';
        enterpriseDropdown.innerHTML = '';
        enterpriseDropdown.disabled = true;
        return;
    }

    // handle comparison and differences of consumer details (in case of consumer type = enterprise or public service)

    let loadList = '';
    switch (firstType) {
        case 'household':
            consumerDropdown.value = 'H';
            enterpriseDropdown.innerHTML = '';
            enterpriseDropdown.disabled = true;
            break;
        case 'public_service':
            consumerDropdown.value = 'P';
            loadList = public_service_list;
            break;
        case 'enterprise':
            consumerDropdown.value = 'E';
            loadList = enterprise_list;
            break;
        case 'power-house':
            consumerDropdown.value = '';
            enterpriseDropdown.innerHTML = '';
            enterpriseDropdown.disabled = true;
            break;
        default:
            console.error("Invalid consumer type (firstType): " + firstType);
    }

    if (loadList != '') {
        const details = selectedMarkers.map(m => m.consumer_detail).filter(Boolean);
        let selectedKey ='';
        if (selectedMarkers.length === 1 && details.length == 1) {
            // single click
            selectedKey = undefined;
        } else {
            // multi click
            const uniqueDetails = [...new Set(details)];
            if (uniqueDetails.length === 0) {
                selectedKey = undefined;
            } else if (uniqueDetails.length === 1 && details.length === selectedMarkers.length) {
                selectedKey = getKeyByValue(loadList, uniqueDetails[0]);
            } else {
                selectedKey = null;
            }
        }
        dropDownMenu(loadList, selectedKey);
    }

    // handle comparison and differences of shs options (optimize and grid)

    const shs_options = selectedMarkers.map(m => m.shs_options).filter(Boolean);
    if (selectedMarkers.length === 1 && !shs_options.length) {
        // single click
        shsOptionsDropdown.value = 'optimize';
    } else {
        // multi click
        const uniqueShsOptions = [...new Set(shs_options)];
        if (uniqueShsOptions.length === 0) {
            shsOptionsDropdown.value = 'optimize';
        } else if (uniqueShsOptions.length === 1 && shs_options.length === selectedMarkers.length) {
            switch (shs_options) {
                case 0:
                    shsOptionsDropdown.value = 'optimize';
                    break;
                case 1:
                    shsOptionsDropdown.value = 'grid';
                    break;
                default:
                    console.error("Invalid shs Option (firstShsOption): " + firstShsOption);
            }
        } else {
            shsOptionsDropdown.value = '';
        }
    }
}

function move_marker() {
    // atm only single markers can be moved, but by parsing over all selected markers it should be possible to
    // move multiple markers at once, if wished and the UI is therefore updated
    selectedMarkers.forEach(marker => {
        old_marker = JSON.parse(JSON.stringify(marker));
        marker.longitude = parseFloat(document.getElementById('longitude').value);
        marker.latitude = parseFloat(document.getElementById('latitude').value);
        map.eachLayer(function (layer) {
            if (layer instanceof L.Marker) {
                let markerLatLng = layer.getLatLng();
                if (markerLatLng.lat === old_marker.latitude && markerLatLng.lng === old_marker.longitude) {
                    map.removeLayer(layer);
                    let markerIcon;
                    if (marker.node_type === 'power-house') {
                        markerIcon = markerPowerHouseSelected;
                    } else {
                        markerIcon = markerConsumerSelected;
                    }
                    L.marker([marker.latitude, marker.longitude], {icon: markerIcon})
                        .on('click', markerOnClick)
                        .addTo(map);
                }
            }
        });
    });
}

document.getElementById('latitude').addEventListener('change', move_marker);
document.getElementById('longitude').addEventListener('change', move_marker);

function deleteAllElements() {
    // empties the UI list
    var listDiv = document.getElementById('load_list');
    listDiv.innerHTML = '';
}

function deleteOneElement(listItem) {
    // deletes 1 load item from the UI and from the marker
    let loadText = listItem.textContent;
    loadText = loadText.replace('Delete', '').trim();
    listItem.remove();

    selectedMarkers.forEach(marker => {
        if (!marker.custom_specification) return;
        let loads = marker.custom_specification
            .split(';')
            .map(l => l.trim())
            .filter(l => l.length > 0);

        loads = loads.filter(l => l !== loadText);
        marker.custom_specification = loads.join(';');
    });
}

function activate_large_loads(delete_list_elements = true) {
    if (delete_list_elements == true) {
        deleteAllElements();
    }
    document.getElementById('loads').innerHTML = option_load;
    document.getElementById('loads').disabled = false;
    document.getElementById('add').disabled = false;
    document.getElementById('number_loads').disabled = false;
}


function deactivate_large_loads() {
    deleteAllElements();
    document.getElementById('loads').disabled = true;
    document.getElementById('loads').value = "";
    document.getElementById('add').disabled = true;
    document.getElementById('number_loads').disabled = true;
}


function large_loads_to_string() {
    let load_list = document.getElementById("load_list");
    let list_items = load_list.getElementsByTagName("div");
    let texts = [];
    for (let i = 0; i < list_items.length; i++) {
        let text = list_items[i].textContent.trim();
        text = text.replace('Delete', '').trim();
        texts.push(text);
    }
    let concatenated_text = texts.join(";");
    return concatenated_text;
}

function getCommonLoads(markers) {
    if (markers.length === 0) return [];

    const loadSets = markers.map(marker => {
        if (!marker.custom_specification) return [];
        return marker.custom_specification.split(";").map(l => l.trim());
    });

    return loadSets.reduce((common, current) =>
        common.filter(load => current.includes(load))
    );
}


function fillList(concatenated_text) {
    let texts = concatenated_text.split(";");
    for (let i = 0; i < texts.length; i++) {
        addElementToLargeLoadList(texts[i]);
    }
}


function addElementToLargeLoadList(customText) {
    // adds a new Element with attached Delete Button to only the DOM element of large loads
    var dropdown = document.getElementById('loads');
    var selectedValue = dropdown.options[dropdown.selectedIndex].text;
    var inputValue = document.getElementById('number_loads').value;
    var list = document.getElementById('load_list');
    var newItem = document.createElement('div');
    var newButton = document.createElement('button');
    newButton.classList.add('right-align');
    newButton.textContent = 'Delete';
    newButton.onclick = function () {
        deleteOneElement(newItem);
    };

    if (customText) {
        newItem.textContent = customText + '    ';
    } else {
        newItem.textContent = inputValue + ' x ' + selectedValue + '    ';
    }

    newItem.appendChild(newButton);
    newItem.style.marginBottom = '10px';
    list.appendChild(newItem);
    if (!customText) {
        document.getElementById('number_loads').value = '1';
    }
};

function saveNewLoadItemToList() {
    // is called by "add" Button, saves the load elements from the DOM to the marker nodes
    addElementToLargeLoadList(customText = undefined);
    let large_load_string = large_loads_to_string();
    selectedMarkers.forEach((marker, i) => {
        marker.custom_specification = large_load_string;
    });
}

// TODO just use boostraps action attributes for this
function expandAccordionItem2() {
    const accordion = new bootstrap.Collapse(document.getElementById('collapseTwo'), {
        toggle: false
    });
    accordion.show();
}


document.getElementById('toggleswitch2').addEventListener('change', function (event) {
    const accordionItem3 = new bootstrap.Collapse(document.getElementById('collapseThree'), {
        toggle: false
    });

    if (event.target.checked) {
        accordionItem3.show();
    } else {
        accordionItem3.hide();
    }
});

$('#collapseTwo').on('hidden.bs.collapse', function () {
    document.getElementById('toggleswitch2').checked = false;
});

document.querySelector('#headingTwo .accordion-button').addEventListener('click', function () {
    const accordionItem2 = document.getElementById('collapseTwo');
    const accordionItem3 = new bootstrap.Collapse(document.getElementById('collapseThree'), {
        toggle: false
    });
    const toggleSwitch2 = document.getElementById('toggleswitch2');

    // Check if the accordion item 2 is currently collapsed
    if (!accordionItem2.classList.contains('show')) {
        accordionItem3.hide();
    } else if (toggleSwitch2.checked) {
        accordionItem3.show();
    }
});

function delete_consumer() {
    let lat = parseFloat(document.getElementById('latitude').value);
    let lng = parseFloat(document.getElementById('longitude').value);
    map_elements = map_elements.filter(function (obj) {
        return obj.latitude !== lat && obj.longitude !== lng;
    });
    map.eachLayer(function (layer) {
        if (layer instanceof L.Marker) {
            let markerLatLng = layer.getLatLng();
            if (markerLatLng.lat === lat && markerLatLng.lng === lng) {
                map.removeLayer(layer);
            }
        }
    });
    document.getElementById('consumer').value = '';
    document.getElementById('consumer').disabled = true;
    document.getElementById('enterprise').value = '';
    document.getElementById('enterprise').disabled = true;
    document.getElementById('shs_options').value = '';
    document.getElementById('shs_options').disabled = true;
    document.getElementById('longitude').value = '';
    document.getElementById('latitude').value = '';
    document.getElementById('longitude').disabled = true;
    document.getElementById('latitude').disabled = true;
    count_consumers();
}


var targetNode = document.getElementById('responseMsg');
var config = {childList: true, subtree: true, characterData: true};
var callback = function (mutationsList, observer) {
    for (let mutation of mutationsList) {
        if ((mutation.type === 'childList' || mutation.type === 'characterData') && targetNode.textContent.trim() !== '') {
            var modal = document.getElementById('msgBox');
            modal.style.display = "block";
        }
    }
};
var observer = new MutationObserver(callback);
observer.observe(targetNode, config);

function stopVideo() {
    var video = document.getElementById("tutorialVideo");
    video.pause();
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
        await file_nodes_to_js(formData);

        // Clear the file input value to allow selecting the same file again
        document.getElementById('fileInput').value = '';
    }
});
