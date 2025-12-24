// ================= MAP INIT =================
const map = L.map("map").setView([16.0471, 108.2068], 6);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

let clickMarker = null;

// ================= CLICK MAP → CHATBOT =================
map.on("click", async function (e) {
  const lat = e.latlng.lat;
  const lng = e.latlng.lng;

  if (clickMarker) map.removeLayer(clickMarker);
  clickMarker = L.marker([lat, lng]).addTo(map);

  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`
    );
    const data = await res.json();

    const place =
      data.address.city ||
      data.address.town ||
      data.address.village ||
      data.address.county ||
      data.display_name;

    const question =
      `Giới thiệu văn hóa, lịch sử địa phương, con người, du lịch, ẩm thực và lịch trình tại ${place}`;

    // Gửi sang chatbot như người dùng gõ
    const input = document.getElementById("msg");
    const sendBtn = document.getElementById("send");

    input.value = question;
    sendBtn.click();

  } catch (err) {
    console.error("Reverse geocode error:", err);
  }
});
