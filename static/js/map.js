const map = L.map('map').setView([16.047079, 108.20623], 6);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution:'© OpenStreetMap'
}).addTo(map);

let marker;

async function searchMap(){
  const q = document.getElementById("mapSearch").value.trim();
  if(!q) return;

  const r = await fetch(`/search-location?q=${encodeURIComponent(q)}`);
  const j = await r.json();

  if(marker) map.removeLayer(marker);

  marker = L.marker([j.lat, j.lng]).addTo(map)
    .bindPopup(`<b>${j.title}</b><br>${j.address}`)
    .openPopup();

  map.setView([j.lat, j.lng], 13);
}
