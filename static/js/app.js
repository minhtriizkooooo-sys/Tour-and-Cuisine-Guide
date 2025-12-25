let map, marker;
const defaultCenter = { lat: 10.8231, lng: 106.6297 };

document.addEventListener("DOMContentLoaded", () => {

    /* ================= MAP ================= */
    map = new google.maps.Map(document.getElementById("map"), {
        center: defaultCenter,
        zoom: 12
    });

    const input = document.getElementById("place-input");
    const autocomplete = new google.maps.places.Autocomplete(input);
    autocomplete.bindTo("bounds", map);

    autocomplete.addListener("place_changed", () => {
        const place = autocomplete.getPlace();
        if (!place.geometry) return;

        if (marker) marker.setMap(null);

        map.panTo(place.geometry.location);
        map.setZoom(15);

        marker = new google.maps.Marker({
            map,
            position: place.geometry.location
        });

        addBot(`📍 <b>${place.name}</b><br>
        Bạn có thể hỏi tôi về lịch trình, văn hóa hoặc ẩm thực nơi này.`);
    });

    /* ================= CHAT ================= */
    const chatBox = document.getElementById("chat-box");
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");

    function addUser(text) {
        const div = document.createElement("div");
        div.className = "user";
        div.innerText = text;
        chatBox.appendChild(div);
        div.scrollIntoView();
    }

    function addBot(text) {
        const div = document.createElement("div");
        div.className = "bot";
        div.innerHTML = text.replace(/\n/g, "<br>");
        chatBox.appendChild(div);
        div.scrollIntoView();
    }

    chatForm.addEventListener("submit", e => {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg) return;

        addUser(msg);
        chatInput.value = "";

        fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msg })
        })
        .then(res => res.json())
        .then(data => addBot(data.reply))
        .catch(() => addBot("⚠️ Không kết nối được chatbot."));
    });

});
