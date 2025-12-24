// ================= MAP INIT =================
const map = L.map("map").setView([16.0471, 108.2068], 6);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

let clickMarker = null;
let currentPlace = null;

// ================= UTILS =================
async function reverseGeocode(lat, lng) {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`
  );
  return res.json();
}

function askChatbot(question) {
  const input = document.getElementById("msg");
  const sendBtn = document.getElementById("send");

  input.value = question;
  sendBtn.click();
}

// ================= CLICK MAP → CHATBOT =================
map.on("click", async (e) => {
  const { lat, lng } = e.latlng;

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

    const question =
      `Giới thiệu văn hóa, lịch sử địa phương, con người, du lịch, ẩm thực và lịch trình tại ${place}`;

    askChatbot(question);

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

// ================= POI LAYER =================
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
    const question =
      `Giới thiệu chi tiết ${name} về lịch sử, đặc trưng, trải nghiệm và gợi ý tham quan`;

    askChatbot(question);
  });
}
