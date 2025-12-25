// ===============================
// app.js – CHAT + MAP (UNIFIED)
// ===============================

let map;
let markers = [];

// ---------------- INIT ----------------
document.addEventListener("DOMContentLoaded", () => {
    initMap();
    bindChat();
});

// ---------------- CHAT ----------------
function bindChat() {
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
    const box = document.getElementById("chat-box");

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

        // Auto search map theo nội dung chat
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

// ---------------- MAP ----------------
function initMap() {
    map = new google.maps.Map(document.getElementById("map"), {
        center: { lat: 10.7769, lng: 106.7009 },
        zoom: 13
    });
}

async function searchMap(query) {
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
    }
}

function clearMarkers() {
    markers.forEach(m => m.setMap(null));
    markers = [];
}

// ---------------- PLACE DETAIL ----------------
async function loadPlaceDetail(place) {
    const res = await fetch(
        `/api/place_detail?place_id=${place.place_id}&name=${encodeURIComponent(place.name)}`
    );
    const d = await res.json();

    document.getElementById("place-name").innerText = d.name;
    document.getElementById("place-address").innerText = d.address || "";
    document.getElementById("place-rating").innerText = d.rating || "—";
    document.getElementById("place-culture").innerText = d.culture;
    document.getElementById("place-food").innerText = d.food;

    if (d.image) {
        document.getElementById("place-image").src = d.image;
    }
}
