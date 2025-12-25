/**
 * VIETNAM TRAVEL AI - MAP.JS (FULL UPDATED)
 * Chức năng: Tìm kiếm, Chỉ đường đa phương tiện, Click hỏi chatbot
 */

let startPoint = null;
let endPoint = null;
let routingControl = null;
let allMarkers = []; 

// ================= MAP INIT =================
const map = L.map("map").setView([16.0471, 108.2068], 6);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap"
}).addTo(map);

// ================= UTILS =================
async function reverseGeocode(lat, lng) {
    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`);
    return res.json();
}

async function forwardGeocode(q) {
    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}`);
    return res.json();
}

// Gọi hàm này để gửi câu hỏi sang chat.js
function triggerChat(question) {
    // Ưu tiên dùng window.sendMsg từ chat.js
    if (window.sendMsg) {
        window.sendMsg(question);
    } else {
        const input = document.getElementById("msg");
        const sendBtn = document.getElementById("send");
        if(input && sendBtn) {
            input.value = question;
            sendBtn.click();
        }
    }
}

// Xóa toàn bộ Marker và Route
function clearMapDecorations() {
    allMarkers.forEach(m => map.removeLayer(m));
    allMarkers = [];
    if (routingControl) {
        map.removeControl(routingControl);
        routingControl = null;
    }
    const panel = document.getElementById("route-panel");
    if(panel) panel.remove();
}

// ================= SEARCH BOX =================
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
        
        map.setView([lat, lng], 14);
        clearMapDecorations();

        const marker = L.marker([lat, lng]).addTo(map)
            .bindPopup(`📍 ${p.display_name}`)
            .openPopup();
        allMarkers.push(marker);

        triggerChat(`Giới thiệu chi tiết về ${p.display_name} bao gồm lịch sử, văn hóa và ẩm thực.`);
    } catch (err) {
        console.error("Search error:", err);
    }
}

// ================= NAVIGATION (GOOGLE MAP STYLE) =================
function enableRouteMode() {
    let panel = document.getElementById("route-panel");
    if (panel) {
        panel.remove();
        return;
    }

    // Tạo UI chọn điểm đi/đến và phương tiện
    panel = document.createElement("div");
    panel.id = "route-panel";
    // Style này sẽ được style.css điều khiển, ở đây đặt inline để đảm bảo hiển thị
    panel.innerHTML = `
        <strong style="display:block;margin-bottom:8px;color:#0f9d58">🧭 Chỉ đường du lịch</strong>
        <input id="start-p" placeholder="Nhập điểm bắt đầu..." style="width:100%;margin-bottom:8px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <input id="end-p" placeholder="Nhập điểm đến..." style="width:100%;margin-bottom:8px;padding:8px;border:1px solid #ddd;border-radius:4px;">
        <select id="mode-p" style="width:100%;margin-bottom:10px;padding:8px;border:1px solid #ddd;border-radius:4px;">
            <option value="car">🚗 Ô tô / Taxi</option>
            <option value="motorcycle">🏍 Xe máy (Phượt)</option>
            <option value="plane">✈️ Máy bay (Đường chim bay)</option>
        </select>
        <button onclick="runRouteCalculation()" style="width:100%;background:#0f9d58;color:white;border:none;padding:10px;border-radius:4px;cursor:pointer;font-weight:bold;">TÌM ĐƯỜNG</button>
    `;
    document.querySelector(".map-area").appendChild(panel);
}

async function runRouteCalculation() {
    const sName = document.getElementById("start-p").value;
    const eName = document.getElementById("end-p").value;
    const mode = document.getElementById("mode-p").value;

    if (!sName || !eName) return alert("Vui lòng nhập đủ điểm đi và đến");

    const sRes = await forwardGeocode(sName);
    const eRes = await forwardGeocode(eName);

    if (sRes.length && eRes.length) {
        clearMarkers();
        const p1 = L.latLng(sRes[0].lat, sRes[0].lon);
        const p2 = L.latLng(eRes[0].lat, eRes[0].lon);

        if (mode === 'plane') {
            // Máy bay vẽ đường thẳng nét đứt
            const line = L.polyline([p1, p2], {color: 'red', weight: 4, dashArray: '10, 10'}).addTo(map);
            allMarkers.push(line);
            map.fitBounds(line.getBounds());
            triggerChat(`Tôi muốn bay từ ${sName} đến ${eName}. Hãy tư vấn thủ tục bay và các món ăn tại sân bay.`);
        } else {
            // Ô tô/Xe máy dùng OSRM
            routingControl = L.Routing.control({
                waypoints: [p1, p2],
                routeWhileDragging: false,
                lineOptions: { 
                    styles: [{ color: mode === 'car' ? '#007bff' : '#ffc107', weight: 6 }] 
                },
                addWaypoints: false,
                show: true
            }).addTo(map);
            triggerChat(`Chỉ đường từ ${sName} đến ${eName} bằng ${mode === 'car' ? 'ô tô' : 'xe máy'}. Tư vấn điểm dừng chân đẹp.`);
        }
        document.getElementById("route-panel").remove();
    } else {
        alert("Không định vị được địa điểm đã nhập.");
    }
}

// ================= MAP CLICK HANDLER =================
map.on("click", async (e) => {
    const { lat, lng } = e.latlng;

    // Xóa marker click cũ để không bị rác bản đồ
    const tempMarker = L.marker([lat, lng]).addTo(map);
    allMarkers.push(tempMarker);

    try {
        const data = await reverseGeocode(lat, lng);
        const place = data.display_name;

        // Luôn kích hoạt chatbot khi click vào bất kỳ đâu
        triggerChat(`Hãy giới thiệu chi tiết về khu vực ${place} (tọa độ ${lat.toFixed(4)}, ${lng.toFixed(4)}) bao gồm lịch sử và du lịch.`);
        
        tempMarker.bindPopup(`📍 ${place}`).openPopup();
    } catch (err) {
        triggerChat(`Khu vực tại tọa độ ${lat.toFixed(4)}, ${lng.toFixed(4)} có gì đặc biệt không?`);
    }
});

// Xuất hàm ra global
window.searchMap = searchMap;
window.enableRouteMode = enableRouteMode;
window.clearMarkers = clearMapDecorations;
window.runRouteCalculation = runRouteCalculation;
