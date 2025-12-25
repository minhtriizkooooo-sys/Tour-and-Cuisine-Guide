let startPoint = null;
let endPoint = null;
let routingControl = null;

let clickMarker = null;      // marker khi click map
let searchMarker = null;     // marker khi search
let currentPlace = null;
let placeHistory = [];

// ================= MAP INIT =================
const map = L.map("map").setView([16.0471, 108.2068], 6);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

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

// ================= SEARCH BOX =================
async function searchMap() {
  const q = document.getElementById("mapSearch").value.trim();
  if (!q) return;

  try {
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

    const searchIcon = L.icon({
      iconUrl: "https://maps.gstatic.com/mapfiles/api-3/images/spotlight-poi2.png",
      iconSize: [27, 43],
      iconAnchor: [13, 41]
    });

    searchMarker = L.marker([lat, lng], { icon: searchIcon })
      .addTo(map)
      .bindPopup(`📍 ${placeName}`)
      .openPopup();

    currentPlace = placeName;
    rememberPlace(placeName);

    searchMarker.on("click", () => {
      askChatbot(
        `Dựa trên các địa điểm đã xem: ${getContext()}.
         Giới thiệu chi tiết ${placeName} về lịch sử, văn hóa, con người, ẩm thực và du lịch`
      );
    });

  } catch (err) {
    console.error("Search error:", err);
  }
}

// ================= MAP CLICK HANDLER =================
map.on("click", async (e) => {
  const { lat, lng } = e.latlng;

  // ===== ROUTE MODE =====
  if (window.routeMode) {
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
        show: false
      }).addTo(map);

      window.routeMode = false;
      startPoint = null;
      endPoint = null;
      return;
    }
  }

  // ===== NORMAL MODE (CLICK MAP → CHATBOT) =====
  if (clickMarker) map.removeLayer(clickMarker);
  clickMarker = L.marker([lat, lng]).addTo(map);

  try {
    const data = await reverseGeocode(lat, lng);

    const place =
      data.address.city ||
      data.address.town ||
      data.address.village ||
      data.address.county ||
      data.display_name;

    currentPlace = place;
    rememberPlace(place);

    askChatbot(
      `Dựa trên các địa điểm đã xem: ${getContext()}.
       Giới thiệu văn hóa, lịch sử, con người, du lịch, ẩm thực và lịch trình tại ${place}`
    );

  } catch (err) {
    console.error("Reverse geocode error:", err);
  }
});

// ================= HOVER MAP → PREVIEW =================
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
        .setContent(`<b>${name}</b><br><small>Click để xem chi tiết</small>`)
        .openOn(map);
    } catch {}
  }, 600);
});

// ================= POI =================
const poiLayer = L.layerGroup().addTo(map);

function addPOI(lat, lng, name, type = "poi") {
  const icon = L.icon({
    iconUrl:
      type === "food"
        ? "/static/icons/food.png"
        : "/static/icons/museum.png",
    iconSize: [26, 26]
  });

  const marker = L.marker([lat, lng], { icon }).addTo(poiLayer);

  marker.on("click", () => {
    askChatbot(
      `Giới thiệu chi tiết ${name} về lịch sử, đặc trưng, trải nghiệm và gợi ý tham quan`
    );
  });
}

// ================= ROUTE BUTTON =================
function enableRouteMode() {
  window.routeMode = true;
  startPoint = null;
  endPoint = null;
  alert("🧭 Chọn điểm đi → điểm đến trên bản đồ");
}
