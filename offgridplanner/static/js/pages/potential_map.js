const map = L.map('map').setView([-18.784571809675114, 34.49966395], 5); // Centered on Europe
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
}).addTo(map);

// Make green clusters for Existing, blue clusters for Potential
const existingSitesLayer = L.markerClusterGroup({
  disableClusteringAtZoom: 15,
  iconCreateFunction: (cluster) => {
    return L.divIcon({
      html: `<div class="cluster cluster-green"><span>${cluster.getChildCount()}</span></div>`,
      className: 'cluster-wrapper',
      iconSize: L.point(40, 40)
    });
  }
}).addTo(map);

const potentialSitesLayer = L.markerClusterGroup({
  disableClusteringAtZoom: 15,
  iconCreateFunction: (cluster) => {
    return L.divIcon({
      html: `<div class="cluster cluster-blue"><span>${cluster.getChildCount()}</span></div>`,
      className: 'cluster-wrapper',
      iconSize: L.point(40, 40)
    });
  }
}).addTo(map);

// Custom
const existingMarker = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const newMarker = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

load_minigrid_legend();

let shouldStop = false;

document.addEventListener('DOMContentLoaded', () => {
  const filterForm = document.getElementById("filter-form");
  const startExplorationBtn = document.getElementById("exploration-btn");
  const stopBtn = document.getElementById('stop-btn');

  // Load previous data on first load
  updateResults(table_data, map_data);

  // load existing Minigrids on map
  existing_mgs.forEach(feature => {
  const [lng, lat] = feature.centroid.coordinates;

  const content = `
    <h3>PREVIOUS SITE</h3>
    <p>ID: ${feature.id}</p>
          <p>PV capacity: ${feature.pv_capacity}</p>
          <p>Grid distance: ${feature.status}</p>
    `;

  const marker = L.marker([lat, lng], { icon: existingMarker }).bindPopup(content);
  existingSitesLayer.addLayer(marker);
  });

  //  Add event listeners for start and stop buttons
  stopBtn.addEventListener('click', () => {
     const response = fetch(stopExplorationUrl);
     $("#loading_spinner").hide();
     shouldStop = true;
     startExplorationBtn.disabled = false;
  });

  startExplorationBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    await sendRequest(formData);
  });

  // Add event listener to edit button for exploration sites
  attachEditListeners();
});

async function sendRequest(body) {
  shouldStop = false;
  const response = await fetch(startExplorationUrl, {
    method: "POST",
    headers: { 'X-CSRFToken': csrfToken },
    body: body
  });
  if (!response.ok) {
    console.error("Failed to start exploration");
    return;
  }
  const data = await response.json();
  document.getElementById("exploration-btn").disabled = true;
  document.querySelector('#sites-table').innerHTML = "";
  potentialSitesLayer.clearLayers();

  if (data.status === "FINISHED") {
    updateResults(data.table, data.geojson);
  } else if (data.status === "RUNNING") {
    $("#loading_spinner").show();
    await new Promise(resolve => setTimeout(resolve, 10000)); // wait 10s
    pollExplorationResults();
  }
}

async function pollExplorationResults() {
  while (!shouldStop) {
    const response = await fetch(loadExplorationSitesUrl);
    console.log("Polling exploration data...")

    if (!response.ok) {
      console.error("Failed to fetch exploration results");
      $("#loading_spinner").hide();
      break;
    }

    const data = await response.json();
    updateResults(data.table, data.geojson);

    if (data.status === "FINISHED" || data.status === "STOPPED") {
      $("#loading_spinner").hide();
      break;
    }

    await new Promise(resolve => setTimeout(resolve, 10000)); // wait 10s
  }
  $("#loading_spinner").hide();
}

function updateResults(table_data, map_data) {
  if (table_data !== undefined) {
      // Update table
      document.querySelector('#sites-table').innerHTML = table_data;
      attachEditListeners();
      }
  if (map_data !== undefined) {
      // Update map
      potentialSitesLayer.clearLayers();
      map_data.forEach(feature => {
      let [lng, lat] = feature.geometry.coordinates;
      let id = feature.properties.name;

        const content = `
          <h3>ID: ${id}</h3>
        `;
        const marker = L.marker([lat, lng], { icon: newMarker }).bindPopup(content);
        potentialSitesLayer.addLayer(marker);
    });
  }
  }


function onEachFeature(feature, layer) {
  const props = feature.properties;
  layer.bindPopup(`ID: ${props.id}<br>Buildings: ${props.building_count}<br>Grid Distance: ${props.grid_dist}`);
}


let currentSortIndex = null;
let sortAscending = true;

function sortTable(colIndex, th) {
  const table = document.getElementById("sites-table");
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));

  // Determine sort direction
  if (currentSortIndex === colIndex) {
    sortAscending = !sortAscending;
  } else {
    sortAscending = true;
    currentSortIndex = colIndex;
  }

  // Sort the rows
  rows.sort((a, b) => {
    const valA = a.cells[colIndex].textContent.trim();
    const valB = b.cells[colIndex].textContent.trim();
    const numA = parseFloat(valA);
    const numB = parseFloat(valB);

    if (!isNaN(numA) && !isNaN(numB)) {
      return sortAscending ? numA - numB : numB - numA;
    } else {
      return sortAscending
        ? valA.localeCompare(valB)
        : valB.localeCompare(valA);
    }
  });

  // Reattach rows
  rows.forEach(row => tbody.appendChild(row));

  // Reset all headers
  const headers = th.parentElement.children;
  Array.from(headers).forEach(header => header.classList.remove("asc", "desc"));

  // Set class on current header
  th.classList.add(sortAscending ? "asc" : "desc");
}

function attachEditListeners() {
    document.querySelectorAll('#edit-btn').forEach(button => {
    button.addEventListener('click', async event => {
      const siteId = event.currentTarget.getAttribute("data-site-id");
      try {
        const response = await fetch(populateSiteDataUrl, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ site_id: siteId })  // Optional payload
        });

      const data = await response.json();

      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      } else if (data.error) {
        console.error(data.error);
      }
    } catch (err) {
      console.error("Error in fetch:", err);
    }
  });
 });
}

function load_minigrid_legend() {
  if (typeof legend === 'undefined' || !legend) {
    window.legend = L.control({ position: 'bottomright' });
  } else {
    map.removeControl(legend);
  }

  const labels = [
    {
      img: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
      text: 'Existing minigrid'
    },
    {
      img: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
      text: 'Potential site'
    }
  ];

  legend.onAdd = function () {
    var div = L.DomUtil.create('div', 'info legend');

    labels.forEach(({ img, text }) => {
      div.innerHTML +=
                " <img src=" +
                img +
                " height='16' width='12'>" +
                "&nbsp" +
                text +
                "<br>";
        });
      return div;
    };
  legend.addTo(map);
}
