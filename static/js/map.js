let startPoint = null;
let endPoint = null;
let routingControl = null;

let allMarkers = []; // Mảng quản lý tất cả marker để xóa sạch khi cần
let currentPlace = null;
let placeHistory = [];

// ================= MAP INIT =================
// Khởi tạo bản đồ tập trung vào Việt Nam
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

// Gọi hàm này từ window để đồng bộ với chat.js
function triggerChat(question) {
  if (window.askChatbot) {
    window.askChatbot(question);
  } else {
    // Fallback nếu chat.js chưa load kịp
    const input = document.getElementById("msg");
    const sendBtn = document.getElementById("send");
    if(input && sendBtn) {
        input.value = question;
        sendBtn.click();
    }
  }
}

// Hàm xóa toàn bộ Marker và Route trên bản đồ
function clearMapDecorations() {
    allMarkers.forEach(m => map.removeLayer(m));
    allMarkers = [];
    if (routingControl) {
        map.removeControl(routingControl);
        routingControl = null;
    }
    startPoint = null;
    endPoint = null;
}

// ================= SEARCH BOX (ĐỊNH VỊ & KÍCH HOẠT CHAT) =================
async function searchMap() {
  const q = document.getElementById("mapSearch").value.trim();
  if (!q) return;

  try {
    const results = await forwardGeocode(q);
    if (!results.length) {
      alert("Không tìm thấy địa điểm này");
      return;
    }

    const p = results[0];
    const lat = parseFloat(p.lat);
    const lng = parseFloat(p.lon);
    const placeName = p.display_name;

    // Di chuyển bản đồ đến vị trí tìm thấy
    map.setView([lat, lng], 14);

    // Xóa marker cũ trước khi thêm mới
    clearMapDecorations();

    const marker = L.marker([lat, lng]).addTo(map)
      .bindPopup(`📍 ${placeName}`)
      .openPopup();
    
    allMarkers.push(marker);

    // Kích hoạt chatbot ngay lập tức khi tìm kiếm thành công
    triggerChat(`Giới thiệu chi tiết về ${placeName} bao gồm lịch sử, văn hóa, con người, ẩm thực và gợi ý du lịch.`);

  } catch (err) {
    console.error("Search error:", err);
  }
}

// ================= NAVIGATION (ĐIỀU HƯỚNG) =================
function enableRouteMode() {
  window.routeMode = true;
  clearMapDecorations();
  alert("🧭 Chế độ điều hướng: Click điểm 1 (Bắt đầu) -> Click điểm 2 (Kết thúc)");
}

// ================= MAP CLICK HANDLER =================
map.on("click", async (e) => {
  const { lat, lng } = e.latlng;

  // TRƯỜNG HỢP 1: ĐANG TRONG CHẾ ĐỘ CHỈ ĐƯỜNG
  if (window.routeMode) {
    if (!startPoint) {
      startPoint = e.latlng;
      const m = L.marker(startPoint).addTo(map).bindPopup("📍 Điểm bắt đầu").openPopup();
      allMarkers.push(m);
      return;
    }

    if (!endPoint) {
      endPoint = e.latlng;
      const m = L.marker(endPoint).addTo(map).bindPopup("🏁 Điểm đến").openPopup();
      allMarkers.push(m);

      // Tạo đường đi
      routingControl = L.Routing.control({
        waypoints: [startPoint, endPoint],
        routeWhileDragging: false,
        addWaypoints: false,
        draggableWaypoints: false,
        show: true, // Hiện bảng chỉ dẫn
        lineOptions: {
            styles: [{ color: '#0f9d58', weight: 6 }]
        }
      }).addTo(map);

      window.routeMode = false; // Kết thúc chọn điểm
      return;
    }
  }

  // TRƯỜNG HỢP 2: CLICK BẤT KỲ ĐÂU (KỂ CẢ TRÊN ĐƯỜNG ĐI) ĐỂ HỎI CHATBOT
  const tempMarker = L.marker([lat, lng]).addTo(map);
  allMarkers.push(tempMarker);

  try {
    const data = await reverseGeocode(lat, lng);
    const place = data.display_name;

    triggerChat(`Tôi đang ở tọa độ này (${lat}, ${lng}) gần ${place}. Hãy giới thiệu lịch sử, văn hóa và ẩm thực đặc trưng tại đây.`);
  } catch (err) {
    triggerChat(`Hãy giới thiệu về khu vực tại tọa độ ${lat}, ${lng}`);
  }
});

// Thêm hàm xóa marker vào global để UI gọi
window.clearMarkers = clearMapDecorations;
window.searchMap = searchMap;
window.enableRouteMode = enableRouteMode;
