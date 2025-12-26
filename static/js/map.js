// Khởi tạo bản đồ
var map = L.map('map').setView([10.7769, 106.7009], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
var markers = [];

// Hàm tìm kiếm địa danh trên bản đồ
async function searchLocation() {
    const query = document.getElementById('map-search-input').value;
    if(!query) return;

    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${query}`);
    const data = await res.json();

    if(data.length > 0) {
        const lat = data[0].lat;
        const lon = data[0].lon;
        map.setView([lat, lon], 14);
        let m = L.marker([lat, lon]).addTo(map).bindPopup(query).openPopup();
        markers.push(m);
        
        // Tự động hỏi chatbot về địa danh này
        askChatbot(`Kể cho tôi về lịch sử, văn hóa và ẩm thực của ${query}`);
    }
}

function toggleNavView() {
    const s = document.getElementById('search-box');
    const n = document.getElementById('nav-box');
    s.style.display = (s.style.display === 'none') ? 'block' : 'none';
    n.style.display = (n.style.display === 'none') ? 'block' : 'none';
}

document.getElementById('clear-markers').onclick = () => {
    markers.forEach(m => map.removeLayer(m));
    markers = [];
};
