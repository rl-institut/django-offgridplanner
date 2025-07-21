const map = L.map('map').setView([9.0725, 7.5377], 5); // Centered on Europe
let sites = {};

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
}).addTo(map);

const markers = L.markerClusterGroup();

document.addEventListener('DOMContentLoaded', () => {
  const filterForm = document.getElementById("filter-form");
  const startExplorationBtn = document.getElementById("exploration-btn");
  const stopBtn = document.getElementById('stop-btn');

  markersLayer = L.markerClusterGroup().addTo(map); // Reusable marker layer

    document.getElementById('stop-btn').addEventListener('click', () => {
        const response = fetch(stopExplorationUrl);
        shouldStop = true;
    });

  startExplorationBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    await sendRequest(formData);
    startExplorationBtn.disabled = true;
  });
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
  startExplorationBtn.disabled = true;

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
      }
  if (map_data !== undefined) {
      // Update map
      potentialSitesLayer.clearLayers();
      map_data.forEach(feature => {
        const [lng, lat] = feature.centroid.coordinates;
        const content = `
          <h3>ID: ${feature.id}</h3>
//          <p>Building count: ${feature.pv_capacity}</p>
//          <p>Grid distance: ${feature.status}</p>
        `;
        const marker = L.marker([lat, lng], { icon: newMarker }).bindPopup(content);
        potentialSitesLayer.addLayer(marker);
    });
    }
  }

//const legend = L.control({ position: 'bottomright' });

//legend.onAdd = function () {
//  const div = L.DomUtil.create('div', 'info legend');
//  const grades = [0, 10, 20, 40, 60, 80];
//
//  for (let i = 0; i < grades.length; i++) {
//    div.innerHTML +=
//      `<i style="background:${getColor(grades[i] + 1)}"></i> ` +
//      `${grades[i]}${grades[i + 1] ? '&ndash;' + grades[i + 1] + '<br>' : '+'}`;
//  }
//
//  return div;
//};

//legend.addTo(map);

//function getColor(building_count) {
//  // Customize the ranges as you like
//  return building_count > 80 ? '#800026' :
//         building_count > 60 ? '#BD0026' :
//         building_count > 40 ? '#E31A1C' :
//         building_count > 20 ? '#FD8D3C' :
//         building_count > 10 ? '#FEB24C' :
//                               '#FFEDA0';
//}

function onEachFeature(feature, layer) {
  const props = feature.properties;
  layer.bindPopup(`ID: ${props.id}<br>Buildings: ${props.building_count}<br>Grid Distance: ${props.grid_dist}`);
}

//function pointToLayer(feature, latlng) {
//  return L.circleMarker(latlng, {
//    radius: 8,
//    fillColor: getColor(feature.properties.building_count),
//    color: '#000',
//    weight: 1,
//    opacity: 1,
//    fillOpacity: 0.8
//  });
//}

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
