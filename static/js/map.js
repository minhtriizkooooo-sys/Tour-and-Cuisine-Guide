let startPoint = null;
let endPoint = null;
let routingControl = null;
let clickMarker = null;

let currentPlace = null;              // địa điểm hiện tại (từ map)
let placeHistory = [];

const DEFAULT_PLACE = "TP. Hồ Chí Minh";

// ================= MAP INIT =================
const map = L.map("map").setView([10.8231, 106.6297], 10); // mặc định HCM

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

// ================= UTILS =================
async function reverseGeocode(lat, lng) {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`,
    {
      headers: {
        "Accept": "application/json",
        "User-Agent": "MapTravelApp/1.0"
      }
    }
  );
  if (!res.ok) throw new Error("Reverse geocode failed");
  return res.json();
}

function rememberPlace(place) {
  if (place && !placeHistory.includes(place)) {
    placeHistory.push(place);
  }
}

function getContext() {
  return placeHistory.slice(-3).join(", ");
}

/**
 * LOGIC CHỐT:
 * - Nếu KHÔNG có địa điểm cụ thể → TP.HCM
 * - Nếu CÓ địa điểm cụ thể → dùng đúng địa điểm đó
 */
function resolvePlaceForQuestion(userText = "") {
  // đã click map → ưu tiên địa điểm map
  if (currentPlace) return currentPlace;

  // user có gõ rõ địa danh không?
  if (userText && userText.length > 0) {
    return userText;
  }

  // mặc định
  return DEFAULT_PLACE;
}

function askChatbot(question, place) {
  const input = document.getElementById("msg");
  const sendBtn = document.getElementById("send");
  if (!input || !sendBtn) return;

  input.value =
    `Hãy trả lời CHỈ dựa trên địa điểm: ${place}.
Giới thiệu văn hóa, lịch sử, du lịch, ẩm thực và gợi ý lịch trình ngắn gọn.

Câu hỏi: ${question}`;

  sendBtn.click();
}

// ================= MAP CLICK HANDLER =================
map.on("click", async (e) => {
  const { lat, lng } = e.latlng;

  // ===== ROUTE MODE =====
  if (window.routeMode === true) {
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

  // ===== NORMAL MODE =====
  if (clickMarker) map.removeLayer(clickMarker);
  clickMarker = L.marker([lat, lng]).addTo(map);

  try {
    const data = await reverseGeocode(lat, lng);

    const place =
      data?.address?.city ||
      data?.address?.town ||
      data?.address?.village ||
      data?.address?.county ||
      data?.display_name;

    if (!place) return;

    currentPlace = place;
    rememberPlace(place);

    askChatbot(
      "Giới thiệu tổng quan điểm đến này",
      place
    );

  } catch (err) {
    console.error(err);
  }
});

// ================= USER TEXT INPUT =================
document.getElementById("send")?.addEventListener("click", () => {
  const input = document.getElementById("msg");
  if (!input) return;

  const text = input.value.trim();
  if (!text) return;

  const place = resolvePlaceForQuestion(text);

  askChatbot(text, place);
});

// ================= ROUTE BUTTON =================
function enableRouteMode() {
  window.routeMode = true;
  alert("🧭 Chọn điểm đi → điểm đến trên bản đồ");
}
