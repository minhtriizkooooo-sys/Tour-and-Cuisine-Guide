// ===============================
// app.js – FINAL FIX (MAP + CHAT)
// ===============================

let map;
let markers = [];

/* ========= WAIT GOOGLE MAPS ========= */
function waitForGoogle(cb) {
    if (window.google && google.maps) {
        cb();
    } else {
        setTimeout(() => waitForGoogle(cb), 100);
    }
}

/* ========= INIT ========= */
document.addEventListener("DOMContentLoaded", () => {
    bindChat();
    bindSearch();
    waitForGoogle(initMap);
});

/* ========= MAP ========= */
function initMap() {
    map = new google.maps.Map(document.getElementById("map"), {
        center: { lat: 10.8231, lng: 106.6297 }, // HCM
        zoom: 12
    });
}

async function searchMap(query) {
    if (!query) return;

    const res = await fetch(`/map-search?q=${encodeURIComponent(query)}`);
    const places = await res.json();

    clearMarkers();

    places.forEach(p => {
        const marker = new google.maps.Marker({
            position: { lat: p.lat, lng: p.lng },
            map,
            title: p.name
        });

        marker.addListener("click", () => loadPlaceDetail(p));
        markers.push(marker);
    });

    if (places.length) {
        map.setCenter({ lat: places[0].lat, lng: places[0].lng });
        map.setZoom(14);
    }
}

function clearMarkers() {
    markers.forEach(m => m.setMap(null));
    markers = [];
}

/* ========= PLACE DETAIL ========= */
async function loadPlaceDetail(place) {
    const res = await fetch(
        `/api/place_detail?place_id=${place.place_id}&name=${encodeURIComponent(place.name)}`
    );
    const d = await res.json();

    const content = `
        <strong>${d.name}</strong><br><br>
        <b>Địa chỉ:</b> ${d.address || "—"}<br>
        <b>Đánh giá:</b> ${d.rating || "—"}<br><br>
        <b>Văn hóa:</b><br>${d.culture}<br><br>
        <b>Ẩm thực:</b><br>${d.food}<br><br>
        <button onclick="askChat('${d.name}')">Hỏi chatbot</button>
    `;

    const infowindow = new google.maps.InfoWindow({ content });
    infowindow.open(map);
}

/* ========= CHAT ========= */
function bindChat() {
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const msg = input.value.trim();
        if (!msg) return;

        appendMsg("user", msg);
        input.value = "";

        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ msg })
        });

        const data = await res.json();
        appendMsg("bot", data.reply);

        // tự động tìm map theo nội dung chat
        searchMap(msg);
    });
}

function appendMsg(role, text) {
    const box = document.getElementById("chat-box");
    const div = document.createElement("div");
    div.className = role;
    div.innerHTML = text.replace(/\n/g, "<br>");
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function askChat(place) {
    const input = document.getElementById("chat-input");
    input.value = `Giới thiệu du lịch ${place}`;
    document.getElementById("chat-form").dispatchEvent(new Event("submit"));
}

/* ========= MAP SEARCH INPUT ========= */
function bindSearch() {
    const input = document.getElementById("place-input");
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            searchMap(input.value.trim());
        }
    });
}
