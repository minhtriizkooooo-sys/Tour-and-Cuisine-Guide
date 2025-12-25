let startPoint = null;
let endPoint = null;
let routingControl = null;

let clickMarker = null;
let searchMarker = null;
let currentPlace = null;
let placeHistory = [];

// ================= MAP INIT =================
const map = L.map("map").setView([16.0471, 108.2068], 6);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

// ================= NAVIGATION PANEL =================
const navPanel = L.control({ position: "topright" });
navPanel.onAdd = function () {
  const div = L.DomUtil.create("div", "nav-panel");
  div.innerHTML = `
    <div style="background:#fff;padding:10px;border-radius:8px;max-width:260px">
      <b>🧭 Điều hướng</b><br>
      <select id="travelMode">
        <option value="car">🚗 Ô tô</option>
        <option value="foot">🚶 Đi bộ</option>
      </select>
      <div id="navSummary" style="margin-top:6px;font-size:13px"></div>
      <div id="navSteps" style="max-height:200px;overflow:auto;font-size:13px"></div>
      <button id="btnGoogleNav" style="margin-top:6px;width:100%">Mở Google Maps</button>
    </div>
  `;
  return div;
};
navPanel.addTo(map);

// ================= UTILS =================
async function reverseGeocode(lat, lng) {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`
  );
  return res.json();
}

async function forwardGeocode(q) {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}`
  );
  return res.json();
}

function askChatbot(question) {
  const input = document.getElementById("msg");
  const sendBtn = document.getElementById("send");
  input.value = question;
  sendBtn.click();
}

function rememberPlace(place) {
  if (place && !placeHistory.includes(place)) {
    placeHistory.push(place);
  }
}

function getContext() {
  return placeHistory.slice(-3).join(", ");
}

// ================= SEARCH =================
async function searchMap() {
  const q = document.getElementById("mapSearch").value.trim();
  if (!q) return;

  const results = await forwardGeocode(q);
  if (!results.length) return alert("Không tìm thấy địa điểm");

  const p = results[0];
  const lat = +p.lat;
  const lng = +p.lon;
  const name = p.display_name;

  map.setView([lat, lng], 14);

  if (searchMarker) map.removeLayer(searchMarker);
  searchMarker = L.marker([lat, lng]).addTo(map).bindPopup(name).openPopup();

  currentPlace = name;
  rememberPlace(name);

  searchMarker.on("click", () => {
    askChatbot(
      `Dựa trên các địa điểm đã xem: ${getContext()}. Giới thiệu chi tiết ${name}`
    );
  });
}

// ================= ROUTING =================
function createRoute(profile = "car") {
  if (routingControl) map.removeControl(routingControl);

  routingControl = L.Routing.control({
    waypoints: [startPoint, endPoint],
    router: L.Routing.osrmv1({
      serviceUrl: "https://router.project-osrm.org/route/v1",
      profile
    }),
    addWaypoints: false,
    draggableWaypoints: false,
    show: false
  })
    .on("routesfound", (e) => {
      const r = e.routes[0];
      const km = (r.summary.totalDistance / 1000).toFixed(1);
      const min = Math.round(r.summary.totalTime / 60);

      document.getElementById("navSummary").innerHTML =
        `📏 ${km} km – ⏱ ${min} phút`;

      const stepsEl = document.getElementById("navSteps");
      stepsEl.innerHTML = "";

      r.instructions.forEach((i) => {
        const div = document.createElement("div");
        div.innerHTML = "➡️ " + i.text;
        stepsEl.appendChild(div);
      });

      document.getElementById("btnGoogleNav").onclick = () => {
        window.open(
          `https://www.google.com/maps/dir/${startPoint.lat},${startPoint.lng}/${endPoint.lat},${endPoint.lng}`,
          "_blank"
        );
      };
    })
    .addTo(map);
}

// ================= MAP CLICK =================
map.on("click", async (e) => {
  const { lat, lng } = e.latlng;

  if (window.routeMode) {
    if (!startPoint) {
      startPoint = e.latlng;
      L.marker(startPoint).addTo(map).bindPopup("📍 Điểm đi").openPopup();
      return;
    }

    if (!endPoint) {
      endPoint = e.latlng;
      L.marker(endPoint).addTo(map).bindPopup("🏁 Điểm đến").openPopup();

      const mode = document.getElementById("travelMode").value;
      createRoute(mode === "foot" ? "foot" : "car");

      window.routeMode = false;
      return;
    }
  }

  if (clickMarker) map.removeLayer(clickMarker);
  clickMarker = L.marker([lat, lng]).addTo(map);

  const data = await reverseGeocode(lat, lng);
  const place =
    data.address.city ||
    data.address.town ||
    data.address.village ||
    data.display_name;

  currentPlace = place;
  rememberPlace(place);

  askChatbot(
    `Dựa trên các địa điểm đã xem: ${getContext()}. Giới thiệu ${place}`
  );
});

// ================= POI =================
const poiLayer = L.layerGroup().addTo(map);

function addPOI(lat, lng, name) {
  const marker = L.marker([lat, lng]).addTo(poiLayer);
  marker.on("click", () => {
    askChatbot(`Giới thiệu chi tiết ${name}`);
  });
}

// ================= ROUTE MODE BUTTON =================
function enableRouteMode() {
  window.routeMode = true;
  startPoint = null;
  endPoint = null;
  alert("🧭 Click điểm đi → điểm đến");
}
