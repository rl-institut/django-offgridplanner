const map = L.map('map').setView([9.0725, 7.5377], 5); // Centered on Europe
let sites = {};

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18,
}).addTo(map);

const markers = L.markerClusterGroup();

document.addEventListener('DOMContentLoaded', () => {
  const filterForm = document.getElementById("filter-form");
  const filterBtn = document.getElementById("filter-btn");

  let markersLayer = L.markerClusterGroup().addTo(map); // Reusable marker layer

  const updateMapAndTable = async (event) => {
    event.preventDefault();

    const formData = new FormData(filterForm);

    try {
      const response = await fetch(filterLocationsUrl, {
        method: "post",
        headers: { 'X-CSRFToken': csrfToken },
        body: formData
      });

      if (!response.ok) throw new Error("Failed to fetch content");

      const data = await response.json();

      // Update table
      document.querySelector('#sites-table').innerHTML = data.table;

      // Update map
      markersLayer.clearLayers(); // Remove old markers
      data.geojson.forEach(feature => {
        const [lng, lat] = feature.geometry.coordinates;
        const props = feature.properties;
        const content = `
          <h3>ID: ${props.id}</h3>
          <p>Building count: ${props.building_count}</p>
          <p>Grid distance: ${props.grid_dist}</p>
          <a href="${projectSetupUrl}">Create project from site</a>`;
        const marker = L.marker([lat, lng]).bindPopup(content);
        markersLayer.addLayer(marker);
      });
    } catch (error) {
      console.error('Error loading content:', error);
    }
  };

  // Bind the submit handler
  filterForm.addEventListener('submit', updateMapAndTable);

  // Trigger the filter on first load
  filterBtn.click();
});

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
