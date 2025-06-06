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

    // Add event listener to the dropdown menu
    document.getElementById('consumer').addEventListener('change', function() {
        count_consumers();
    });
})();


let enterprise_option = '';

function dropDownMenu(dropdown_list) {
    enterprise_option = '';
    for (let enterprise_code in dropdown_list) {
        let selected = (enterprise_code == consumer_type) ? ' selected' : '';
        enterprise_option += '<option value="' + enterprise_code + '"' + selected + '>' + dropdown_list[enterprise_code] + '</option>';
        document.getElementById('enterprise').innerHTML = enterprise_option;
        document.getElementById('enterprise').disabled = false;
    }
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

document.getElementById('consumer').addEventListener('change', function () {
    if (this.value === 'H') {
        document.getElementById('enterprise').value = '';
        document.getElementById('enterprise').disabled = true;
        deactivate_large_loads();
    } else if (this.value === 'E') {
        dropDownMenu(enterprise_list);
        document.getElementById('enterprise').innerHTML = enterprise_option;
        document.getElementById('enterprise').value = 'group1';
        document.getElementById('enterprise').disabled = false;
        activate_large_loads();
    } else if (this.value === 'P') {
        dropDownMenu(public_service_list);
        deactivate_large_loads();
    }
});
document.getElementById('enterprise').disabled = true;
document.getElementById('consumer').disabled = true;
document.getElementById('enterprise').value = '';
document.getElementById('consumer').value = '';
document.getElementById('shs_options').disabled = true;
document.getElementById('shs_options').value = '';


let markerConsumerSelected = new L.Icon({
    iconUrl: "/static/assets/icons/i_consumer_selected.svg",
    iconSize: [12, 12],
});

let markerPowerHouseSelected = new L.Icon({
    iconUrl: "/static/assets/icons/i_power_house_selected.svg",
    iconSize: [12, 12],
});


let marker
let old_marker

function getKeyByValue(object, value) {
    return Object.keys(object).find(key => object[key] === value);
}

// TODO this can stay
function markerOnClick(e) {
    L.DomEvent.stopPropagation(e);
    if (marker) {
        update_map_elements();
    }
    expandAccordionItem2();
    const index = map_elements.findIndex(obj => obj.latitude === e.latlng.lat && obj.longitude === e.latlng.lng);
    if (index >= 0) {
        marker = map_elements.splice(index, 1)[0];
        old_marker = JSON.parse(JSON.stringify(marker));
    }
    map.eachLayer(function (layer) {
        if (layer instanceof L.Marker) {
            let markerLatLng = layer.getLatLng();
            if (markerLatLng.lat === e.latlng.lat && markerLatLng.lng === e.latlng.lng) {
                map.removeLayer(layer);
                let markerIcon;
                if (marker.node_type === 'power-house') {
                    markerIcon = markerPowerHouseSelected;
                } else {
                    markerIcon = markerConsumerSelected;
                }
                L.marker([markerLatLng.lat, markerLatLng.lng], {icon: markerIcon,})
                    .on('click', markerOnClick).addTo(map);
                document.getElementById('longitude').value = marker.longitude;
                document.getElementById('latitude').value = marker.latitude;
                if (marker.node_type === 'power-house') {
                    document.getElementById('consumer').value = '';
                    document.getElementById('consumer').disabled = true;
                    document.getElementById('shs_options').value = '';
                    document.getElementById('shs_options').disabled = true;
                    document.getElementById('enterprise').disabled = true;
                    document.getElementById('enterprise').value = '';
                    deactivate_large_loads();
                } else if (marker.consumer_type === 'household') {
                    document.getElementById('consumer').value = 'H';
                    document.getElementById('enterprise').disabled = true;
                    document.getElementById('enterprise').value = '';
                    document.getElementById('shs_options').disabled = false;
                    document.getElementById('consumer').disabled = false;
                    deactivate_large_loads();

                } else if (marker.consumer_type === 'enterprise') {
                    dropDownMenu(enterprise_list);
                    document.getElementById('consumer').value = 'E';
                    let key = getKeyByValue(enterprise_list, marker.consumer_detail);
                    document.getElementById('enterprise').value = key;
                    document.getElementById('shs_options').disabled = false;
                    document.getElementById('consumer').disabled = false;
                    activate_large_loads();
                    if (marker.custom_specification.length > 5) {
                        activate_large_loads(false);
                        fillList(marker.custom_specification);
                        document.getElementById('toggleswitch2').checked = true;
                        const accordionItem3 = new bootstrap.Collapse(document.getElementById('collapseThree'), {
                            toggle: false
                        });
                        accordionItem3.show();
                    }
                } else if (marker.consumer_type === 'public_service') {
                    dropDownMenu(public_service_list);
                    document.getElementById('shs_options').disabled = false;
                    document.getElementById('consumer').value = 'P';
                    document.getElementById('consumer').disabled = false;
                    let key2 = getKeyByValue(public_service_list, marker.consumer_detail);
                    document.getElementById('enterprise').value = key2;
                    deactivate_large_loads()
                }
                if (marker.node_type !== 'power-house') {
                    if (marker.shs_options == 0) {
                        document.getElementById('shs_options').value = 'optimize';
                    } else if (marker.shs_options == 1) {
                        document.getElementById('shs_options').value = 'grid';
                    }
                }
                document.getElementById('longitude').disabled = false;
                document.getElementById('latitude').disabled = false;

            }
        }
    });
}

function update_map_elements() {
    let longitude = document.getElementById('longitude').value;
    let latitude = document.getElementById('latitude').value;
    let shs_options = document.getElementById('shs_options').value;
    let shs_value;
    let large_load_string = large_loads_to_string();

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

    if (longitude.length > 0 && latitude.length > 0) {
        marker.longitude = parseFloat(longitude);
        marker.latitude = parseFloat(latitude);
        marker.shs_options = parseInt(shs_value);
        marker.custom_specification = large_load_string;


        let consumerValue = document.getElementById('consumer').value;

        switch (consumerValue) {
            case 'H':
                marker.consumer_type = 'household';
                marker.consumer_detail = 'default';
                selected_icon = markerConsumer;
                break;
            case 'P':
                marker.consumer_type = 'public_service';
                marker.consumer_detail = document.getElementById('enterprise').value;
                let key2 = document.getElementById('enterprise').value;
                marker.consumer_detail = public_service_list[key2];
                selected_icon = markerPublicservice;
                break;
            case 'E':
                marker.consumer_type = 'enterprise';
                let key = document.getElementById('enterprise').value;
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
        map_elements.push(marker);

        map.eachLayer(function (layer) {
            if (layer instanceof L.Marker) {
                let markerLatLng = layer.getLatLng();
                if (markerLatLng.lat === old_marker.latitude && markerLatLng.lng === old_marker.longitude) {
                    map.removeLayer(layer);
                    L.marker([marker.latitude, marker.longitude], {icon: selected_icon})
                        .on('click', markerOnClick).addTo(map);
                }
            }
        });
    }
    count_consumers(false)
}

function move_marker() {
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
}

document.getElementById('latitude').addEventListener('change', move_marker);
document.getElementById('longitude').addEventListener('change', move_marker);

function deleteAllElements() {
    var listDiv = document.getElementById('load_list');
    listDiv.innerHTML = '';
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


function fillList(concatenated_text) {
    let texts = concatenated_text.split(";");
    for (let i = 0; i < texts.length; i++) {
        addElementToLargeLoadList(texts[i]);
    }
}


function addElementToLargeLoadList(customText) {
    var dropdown = document.getElementById('loads');
    var selectedValue = dropdown.options[dropdown.selectedIndex].text;
    var inputValue = document.getElementById('number_loads').value;
    var list = document.getElementById('load_list');
    var newItem = document.createElement('div');
    var newButton = document.createElement('button');
    newButton.classList.add('right-align');
    newButton.textContent = 'Delete';
    newButton.onclick = function () {
        list.removeChild(newItem);
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
