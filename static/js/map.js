// =====================================================
// GLOBAL STATE
// =====================================================
let startPoint = null;
let endPoint = null;
let routingControl = null;

let clickMarker = null;
let searchMarker = null;

let currentPlace = null;
let placeHistory = [];

let routeMode = false;

// =====================================================
// MAP INIT
// =====================================================
const map = L.map("map").setView([16.0471, 108.2068], 6);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

// =====================================================
// GEOCODING
// =====================================================
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

// =====================================================
// CHAT INTEGRATION
// =====================================================
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

// Gửi context địa điểm sang chat.js
function updateChatContext(place) {
  if (window.setPlaceContext) {
    window.setPlaceContext(place);
  }
}

// =====================================================
// SEARCH LOCATION
// =====================================================
async function searchMap() {
  const q = document.getElementById("mapSearch").value.trim();
  if (!q) return;

  const results = await forwardGeocode(q);
  if (!results.length) {
    alert("Không tìm thấy địa điểm");
    return;
  }

  const p = results[0];
  const lat = parseFloat(p.lat);
  const lng = parseFloat(p.lon);
  const placeName = p.display_name;

  map.setView([lat, lng], 14);

  if (searchMarker) map.removeLayer(searchMarker);

  searchMarker = L.marker([lat, lng]).addTo(map)
    .bindPopup(`📍 ${placeName}`)
    .openPopup();

  currentPlace = placeName;
  rememberPlace(placeName);
  updateChatContext(placeName);

  searchMarker.on("click", () => {
    askChatbot(
      `Giới thiệu chi tiết ${placeName} về lịch sử, văn hóa, con người, ẩm thực và du lịch`
    );
  });
}

// =====================================================
// MAP CLICK HANDLER
// =====================================================
map.on("click", async (e) => {

  // ================= ROUTE MODE =================
  if (routeMode) {
    if (!startPoint) {
      startPoint = e.latlng;
      L.marker(startPoint).addTo(map).bindPopup("📍 Điểm xuất phát").openPopup();
      return;
    }

    if (!endPoint) {
      endPoint = e.latlng;
      L.marker(endPoint).addTo(map).bindPopup("🏁 Điểm đến").openPopup();

      if (routingControl) map.removeControl(routingControl);

      routingControl = L.Routing.control({
        waypoints: [startPoint, endPoint],
        routeWhileDragging: false,
        addWaypoints: false,
        show: true,
        lineOptions: {
          styles: [{ weight: 6 }]
        }
      }).addTo(map);

      // Chatbot giới thiệu tuyến đường & vùng đi qua
      askChatbot(
        `Giới thiệu các địa phương, văn hóa, ẩm thực và điểm du lịch nổi bật trên tuyến đường từ điểm xuất phát đến điểm đến này`
      );

      routeMode = false;
      startPoint = null;
      endPoint = null;
      return;
    }
  }

  // ================= NORMAL MODE =================
  if (clickMarker) map.removeLayer(clickMarker);
  clickMarker = L.marker(e.latlng).addTo(map);

  try {
    const data = await reverseGeocode(e.latlng.lat, e.latlng.lng);

    const place =
      data.address.city ||
      data.address.town ||
      data.address.village ||
      data.address.county ||
      data.display_name;

    currentPlace = place;
    rememberPlace(place);
    updateChatContext(place);

    askChatbot(
      `Giới thiệu văn hóa, con người, lịch sử, ẩm thực và gợi ý lịch trình du lịch tại ${place}`
    );

  } catch (err) {
    console.error("Reverse geocode error:", err);
  }
});

// =====================================================
// HOVER PREVIEW
// =====================================================
let hoverTimer = null;
let hoverPopup = L.popup({
  closeButton: false,
  offset: [0, -10]
});

map.on("mousemove", (e) => {
  clearTimeout(hoverTimer);

  hoverTimer = setTimeout(async () => {
    try {
      const data = await reverseGeocode(e.latlng.lat, e.latlng.lng);
      const name =
        data.address.city ||
        data.address.town ||
        data.address.village ||
        data.display_name;

      hoverPopup
        .setLatLng(e.latlng)
        .setContent(`<b>${name}</b><br><small>Click để khám phá</small>`)
        .openOn(map);
    } catch {}
  }, 600);
});

// =====================================================
// ROUTE MODE BUTTON
// =====================================================
function enableRouteMode() {
  routeMode = true;
  startPoint = null;
  endPoint = null;

  if (routingControl) {
    map.removeControl(routingControl);
    routingControl = null;
  }
}

// =====================================================
// EXPORT GLOBAL
// =====================================================
window.searchMap = searchMap;
window.enableRouteMode = enableRouteMode;
