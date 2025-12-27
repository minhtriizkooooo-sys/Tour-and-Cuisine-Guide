<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vietnam Travel AI - Map Explorer</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        :root { --primary-blue: #0077b6; --bg-gray: #f8f9fa; }
        body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; font-family: 'Segoe UI', Tahoma, sans-serif; }

        .main-wrapper { display: flex; height: 100vh; width: 100vw; }
        #map { flex: 1; height: 100%; border-right: 2px solid #ddd; z-index: 1; }

        .chat-container { width: 450px; display: flex; flex-direction: column; background: white; z-index: 10; }
        header { background: var(--primary-blue); color: white; padding: 15px; text-align: center; }
        .chat-box { flex: 1; overflow-y: auto; padding: 20px; background: var(--bg-gray); display: flex; flex-direction: column; gap: 15px; }
        
        .msg { padding: 12px 15px; border-radius: 15px; max-width: 85%; line-height: 1.6; font-size: 14px; position: relative; }
        .msg.user { align-self: flex-end; background: var(--primary-blue); color: white; border-bottom-right-radius: 2px; }
        .msg.bot { align-self: flex-start; background: white; color: #333; border: 1px solid #ddd; border-bottom-left-radius: 2px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }

        .suggestion-row { padding: 10px; display: flex; gap: 8px; flex-wrap: wrap; background: white; border-top: 1px solid #eee; }
        .sug-btn { border: 1px solid var(--primary-blue); background: white; color: var(--primary-blue); padding: 5px 10px; border-radius: 20px; font-size: 12px; cursor: pointer; transition: 0.3s; }
        .sug-btn:hover { background: var(--primary-blue); color: white; }

        .input-group { padding: 15px; display: flex; gap: 10px; border-top: 1px solid #eee; background: white; }
        input { flex: 1; padding: 10px 15px; border-radius: 25px; border: 1px solid #ddd; outline: none; }
        button#send-btn { background: var(--primary-blue); color: white; border: none; width: 40px; height: 40px; border-radius: 50%; cursor: pointer; }

        /* FOOTER THEO YÊU CẦU */
        footer { 
            background: #e0f2fe; /* Xanh trời nhạt */
            padding: 10px; 
            text-align: center; 
            font-size: 12px; 
            color: #444; 
            border-top: 1px solid #bae6fd;
        }
        .designer { color: #0284c7; font-weight: bold; font-size: 13px; text-transform: uppercase; }
    </style>
</head>
<body>

<div class="main-wrapper">
    <div id="map"></div>

    <div class="chat-container">
        <header><h3 style="margin:0"><i class="fas fa-map-marked-alt"></i> Vietnam Travel AI</h3></header>
        <div id="chat-box" class="chat-box">
            <div class="msg bot">Chào bạn! Hãy <b>Click vào bản đồ</b> để tìm hiểu lịch sử, văn hóa và ẩm thực của bất kỳ địa danh nào nhé!</div>
        </div>
        <div id="suggestion-box" class="suggestion-row"></div>
        <div class="input-group">
            <input type="text" id="user-input" placeholder="Hỏi về địa danh, món ăn...">
            <button id="send-btn" onclick="handleSend()"><i class="fas fa-paper-plane"></i></button>
        </div>
        <footer>
            Hotline: {{ HOTLINE }} — Designer: <span class="designer">{{ BUILDER }}</span>
        </footer>
    </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
    // Khởi tạo bản đồ tại Việt Nam
    var map = L.map('map').setView([16.047, 108.206], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

    var currentMarker;

    // Click bản đồ để lấy Marker và hỏi AI
    map.on('click', async function(e) {
        const { lat, lng } = e.latlng;
        if (currentMarker) map.removeLayer(currentMarker);
        currentMarker = L.marker([lat, lng]).addTo(map);
        
        // Reverse Geocoding để lấy tên địa danh từ tọa độ
        try {
            const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`);
            const data = await res.json();
            const place = data.address.city || data.address.province || data.address.state || "địa điểm này";
            handleSend(`Kể cho tôi về lịch sử, con người và ẩm thực tại ${place}`);
        } catch (err) {
            handleSend(`Kể cho tôi về lịch sử và ẩm thực vùng này (Tọa độ ${lat.toFixed(2)}, ${lng.toFixed(2)})`);
        }
    });

    async function handleSend(text = null) {
        const input = document.getElementById('user-input');
        const msg = text || input.value;
        if (!msg) return;
        input.value = "";

        const chatBox = document.getElementById('chat-box');
        chatBox.innerHTML += `<div class="msg user">${msg}</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({msg: msg})
            });
            const data = await response.json();

            chatBox.innerHTML += `<div class="msg bot">${data.text.replace(/\n/g, '<br>')}</div>`;
            
            const sugBox = document.getElementById('suggestion-box');
            sugBox.innerHTML = data.suggestions.map(s => 
                `<button class="sug-btn" onclick="handleSend('${s}')">${s}</button>`
            ).join('');

            chatBox.scrollTop = chatBox.scrollHeight;
        } catch (e) {
            chatBox.innerHTML += `<div class="msg bot">Lỗi kết nối server.</div>`;
        }
    }

    document.getElementById('user-input').addEventListener('keypress', (e) => { if(e.key === 'Enter') handleSend(); });
</script>
</body>
</html>
