/**
 * The script integrates interactive drawing tools into a Leaflet.js map withina FastAPI web application. Primarily
 * utilized on the "consumer-selection" page, it empowers users to draw markers, rectangles, and polygons on the
 * map. These drawings are crucial for designating consumer locations and marking
 * specific areas of interest.
 *
 * Key Features:
 * - Polygon and Rectangle Drawing: Enables users to draw polygons and rectangles on the map with predefined
 *   shape and color settings, enhancing the map's interactivity and user engagement.
 *
 * - Custom Marker Controls: Facilitates the addition of distinct icons, such as power houses or consumers,
 *   onto the map, allowing for a more detailed and customized mapping experience.
 *
 * - Event Listeners: Actively listens for and responds to the creation of new shapes or markers. It ensures
 *   that the map elements are updated in real time, reflecting user actions instantaneously.
 *
 * - Dynamic Marker Management: Provides functionalities to dynamically add or remove markers based on user
 *   interactions, offering a flexible and responsive user interface.
 *
 * - Trash Bin Control: Incorporates a custom control to clear all drawn items from the map, simplifying the
 *   process of resetting or starting a new selection.
 *
 * - GeoSearch Integration: Utilizes the GeoSearch library to enable location searching capabilities,
 *   enhancing the usability and functionality of the map.
 *
 * - Consumer Toggle Feature: Includes a toggle mechanism to switch between adding and removing consumers
 *   from the map, offering versatility in map manipulation.
 *
 * - Consumer Count Display: Counts and displays the number of consumers currently present on the map, providing
 *   valuable insights at a glance.
 */

var polygonDrawer = new L.Draw.Polygon(map, {
    shapeOptions: {
        color: '#1F567D80'
    }
});

var rectangleDrawer = new L.Draw.Rectangle(map, {
    shapeOptions: {
        color: '#1F567D80'
    }
});


let isPowerHouseMarker = false

var myCustomMarker = L.Icon.extend({
    options: {
        shadowUrl: null,
        iconAnchor: new L.Point(12, 12),
        iconSize: new L.Point(24, 24),
        iconUrl: "/static/icons/i_consumer.svg"
    }
});


const iconB = L.icon({
    iconUrl: "/static/icons/i_power_house.svg",
    iconSize: [12, 12], // size of the icon
    iconAnchor: [12, 12], // point of the icon which will correspond to marker's location
    popupAnchor: [1, -12] // point from which the popup should open relative to the iconAnchor
});


L.NewMarker = L.Draw.Marker.extend({
    options: {
        icon: iconB
    }
});


let drawControl = new L.Control.Draw({
    position: 'topleft',
    draw: {
        polyline: false,
        polygon: true,
        circle: false,
        circlemarker: false,
        rectangle: true,
        marker: {
            icon: new myCustomMarker
        }
    }
});


const CustomMarkerControl = L.Control.extend({
    options: {
        position: 'topleft'
    },

    onAdd: function (map) {
        const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
        L.DomEvent.disableClickPropagation(container);

        const link = L.DomUtil.create('a', 'leaflet-draw-draw-marker', container);
        link.href = '#';
        link.title = 'place power-house';

        // add an image inside the link
        const image = L.DomUtil.create('img', 'my-marker-icon', link);
        image.src = '/static/icons/i_power_house_grey.svg';
        image.alt = 'Marker';
        image.style.width = '12px';
        image.style.height = '12px';

        L.DomEvent.on(link, 'click', L.DomEvent.stop)
            .on(link, 'click', function () {
                isPowerHouseMarker = true;

                // Disable any active drawing layer.
                for (let type in drawControl._toolbars.draw._modes) {
                    if (drawControl._toolbars.draw._modes[type].handler.enabled()) {
                        drawControl._toolbars.draw._modes[type].handler.disable();
                    }
                }

                new L.Draw.Marker(map, {icon: iconB}).enable();
            });


        return container;
    }
});



L.Control.Trashbin = L.Control.extend({
    options: {
        position: 'topleft',
    },

    onAdd: function () {
        const container = L.DomUtil.create('div', 'leaflet-control-trashbin leaflet-bar');
        const link = L.DomUtil.create('a', '', container);
        link.href = '#';
        link.title = 'Clear all';
        link.innerHTML = '🗑'; // Use the HTML entity for the trash bin icon (U+1F5D1)

        L.DomEvent.on(link, 'click', L.DomEvent.stopPropagation)
            .on(link, 'click', L.DomEvent.preventDefault)
            .on(link, 'click', () => {
                const modal = document.getElementById('msgBox');
                const message = document.getElementById('responseMsg');
                const confirmBtn = document.getElementById('confirmDelete');
                const cancelBtn = document.getElementById('cancelDelete');
                const okBtn = modal.querySelector('.deletebtn:not(#confirmDelete)');

                message.innerHTML = gettext('Are you sure? This action will delete all consumers. To delete only selected, please use the button on the consumer properties bar.');
                confirmBtn.style.display = 'inline-block';
                cancelBtn.style.display = 'inline-block';
                okBtn.style.display = 'none';

                confirmBtn.onclick = () => {
                    modal.style.display = 'none';
                    customTrashBinAction();
                };
                cancelBtn.onclick = () => {
                    modal.style.display = 'none';
                };

                modal.style.display = 'block';
            });
        return container;
    },
});

function customTrashBinAction() {
    removeBoundaries();
    remove_marker_from_map();
    polygonCoordinates = [];
    map_elements = [];
    selectedMarkers = [];
}

const trashbinControl = new L.Control.Trashbin();


const searchProvider = new GeoSearch.OpenStreetMapProvider();

const searchControl = new GeoSearch.GeoSearchControl({
    provider: searchProvider,
    position: 'topleft',
    showMarker: false,
});


const searchInput = document.getElementById('search-input');

searchInput.addEventListener('keypress', async (event) => {
    if (event.key === 'Enter') {
        event.preventDefault();
        let query = searchInput.value;
        if (!query) return;

        let results = await searchProvider.search({query});
        if (results && results.length > 0) {
            const {x: lng, y: lat} = results[0];

            if (isLatLngInMapBounds(lat, lng)) {
                map.setView([lat, lng], 13);
            } else {
                const responseMsg = document.getElementById("responseMsg");
                if (responseMsg) {
                    responseMsg.innerHTML = 'Location not inside country bounds';
                }
            }
        } else {
            alert('No results found');
        }
    }
});

function isLatLngInMapBounds(lat, lng) {
    const latLng = L.latLng(lat, lng);
    return map.options.maxBounds.contains(latLng);
}

let input = document.getElementById('toggleswitch');


function removeBoundaries() {
    drawnItems.clearLayers();
    polygonCoordinates = [];
}


var customControl = L.Control.extend({
    options: {
        position: 'bottomleft'
    },

    onAdd: function (map) {
        var container = L.DomUtil.create('div', 'my-custom-control');

        // Create the form
        var form = L.DomUtil.create('form', 'my-form', container);
        var label = L.DomUtil.create('label', '', form);
        label.textContent = 'Remove Consumers: ';
        var input = L.DomUtil.create('input', '', form);
        input.type = 'checkbox';

        // When the input changes, toggle your feature
        L.DomEvent.on(input, 'change', function () {
            is_active = !is_active;  // Toggle the is_active variable
            // TODO: Add your code here to do something with the map when the toggle changes
        });

        return container;
    }
});



function addDrawingToolsToConsumerMap() {
    map.addControl(new CustomMarkerControl());
    map.addControl(trashbinControl);
    map.addControl(searchControl);
    map.addControl(new customControl());
    map.addControl(drawControl);
}
