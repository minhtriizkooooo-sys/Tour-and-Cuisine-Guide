var map = L.map('map').setView([10.7769, 106.7009], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

var markers = [];

map.on('click', function(e) {
    let m = L.marker(e.latlng).addTo(map);
    markers.push(m);
    // Gửi tọa độ này qua Chatbot để nó tìm địa danh gần nhất và trả lời
    askChatbot(`Địa điểm tại tọa độ ${e.latlng.lat}, ${e.latlng.lng}`);
});

document.getElementById('clear-markers').onclick = () => {
    markers.forEach(m => map.removeLayer(m));
    markers = [];
};

