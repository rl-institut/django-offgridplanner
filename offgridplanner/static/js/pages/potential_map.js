const filterControl = L.control({ position: 'topleft' });

const map = L.map('map').setView([9.0725, 7.5377], 5); // Centered on Europe
let sites = {};

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
}).addTo(map);

const markers = L.markerClusterGroup();

document.addEventListener('DOMContentLoaded', () => {
  const filterForm = document.getElementById("filter-form");

  filterForm.addEventListener('submit', async (event) => {
    event.preventDefault(); // prevent the default behavior (e.g., link navigation)
    const formData = new FormData(filterForm);

    console.log(Object.fromEntries(formData.entries()));
    try {
      const response = await fetch(filterLocationsUrl,
          {
              method: "post",
              headers: {'X-CSRFToken': csrfToken },
              body: formData
          });
      if (!response.ok)
      {
          throw new Error('Failed to fetch content');
      }

      const data = await response.json();
      document.querySelector('#sites-table').innerHTML = data.table;
    } catch (error) {
      console.error('Error loading content :', error);
    }
  });
  // click button once upon loading the page
  document.getElementById("filter-btn").click()
});

fetch(siteLocationsUrl)
  .then(response => response.json())
  .then(data => {
      sites = data.features;
      data.features.forEach(feature => {
          const coords = feature.geometry.coordinates;
          const props = feature.properties;
          const content = `<h3>ID: ${props.name}</h3><p>Building count: ${props.building_count}</p><p>Grid distance: ${props.grid_dist}</p><a href=${projectSetupUrl}>Create project from site</a>`;
          const marker = L.marker([coords[1], coords[0]])
          .bindPopup(content);
          markers.addLayer(marker);
      });
      map.addLayer(markers);
  });

filterControl.onAdd = function () {
  const div = L.DomUtil.create('div', 'filter-control');
  div.innerHTML = `
    <label for="buildingFilter">Min Buildings</label><br>
    <input type="range" id="buildingFilter" min="0" max="1000" value="0" step="1">
    <span id="filterValue">0</span>
  `;
  return div;
};

filterControl.addTo(map);

// Prevent map dragging when interacting with slider
L.DomEvent.disableClickPropagation(filterControl.getContainer());

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
