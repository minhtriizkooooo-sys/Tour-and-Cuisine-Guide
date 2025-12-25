const SESSION_ID = Math.random().toString(36).substring(7);

// HÀM GỬI TIN NHẮN (Đưa ra global để map.js gọi được)
async function sendMsg(customText = null) {
    const input = document.getElementById("msg");
    const messagesEl = document.getElementById("messages");
    const suggestionsEl = document.getElementById("suggestions");

    const text = customText || input.value.trim();
    if (!text) return;

    // Hiển thị tin user
    appendBubble("user", text);
    input.value = "";
    suggestionsEl.innerHTML = "";

    const loading = appendBubble("bot", "Đang kết nối dữ liệu thực tế...");

    try {
        const r = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ msg: text, sid: SESSION_ID })
        });
        const j = await r.json();
        loading.remove();

        appendBubble("bot", j.reply);
        if (j.images) renderImages(j.images);
        if (j.suggestions) renderSuggestions(j.suggestions);

    } catch (e) {
        if(loading) loading.remove();
        appendBubble("bot", "⚠️ Lỗi kết nối API. Hãy kiểm tra lại API Key trong app.py");
    }
}

function appendBubble(role, text) {
    const messagesEl = document.getElementById("messages");
    const b = document.createElement("div");
    b.className = "bubble " + role;
    b.innerText = text;
    messagesEl.appendChild(b);
    messagesEl.scrollTop = messagesEl.scrollHeight; // Tự động cuộn xuống
    return b;
}

function renderImages(images) {
    const messagesEl = document.getElementById("messages");
    if (!images || !images.length) return;
    const row = document.createElement("div");
    row.className = "img-row";
    images.forEach(img => {
        const el = document.createElement("img");
        el.src = img.url;
        el.className = "img-item";
        el.onclick = () => {
            const modal = document.getElementById("img-modal");
            document.getElementById("img-modal-src").src = img.url;
            document.getElementById("img-modal-caption").innerText = img.caption || "";
            modal.style.display = "flex";
        };
        row.appendChild(el);
    });
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderSuggestions(list) {
    const suggestionsEl = document.getElementById("suggestions");
    suggestionsEl.innerHTML = "";
    list.forEach(s => {
        const btn = document.createElement("button");
        btn.innerText = s;
        btn.onclick = () => sendMsg(s);
        suggestionsEl.appendChild(btn);
    });
}

// Gắn vào window cho Map.js gọi
window.sendMsg = sendMsg;
window.askChatbot = sendMsg;

document.addEventListener("DOMContentLoaded", () => {
    // ĐÓNG MODAL TUYỆT ĐỐI
    document.addEventListener("click", (e) => {
        const modal = document.getElementById("img-modal");
        if (!modal) return;
        if (e.target.id === "img-close" || e.target === modal) {
            modal.style.display = "none";
        }
    });

    document.getElementById("send").onclick = () => sendMsg();
    document.getElementById("msg").onkeydown = (e) => { if(e.key === "Enter") sendMsg(); };

    // XUẤT PDF
    document.getElementById("btn-export").onclick = async () => {
        const r = await fetch("/export-pdf", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ sid: SESSION_ID })
        });
        const blob = await r.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "Lich_su_hanh_trinh.pdf"; a.click();
    };
});
