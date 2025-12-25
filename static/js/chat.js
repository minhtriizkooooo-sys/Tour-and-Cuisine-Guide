const SESSION_ID = Math.random().toString(36).substring(7);

// Đưa hàm ra Global
async function sendMsg(customText = null) {
    const input = document.getElementById("msg");
    const container = document.getElementById("messages");
    const suggestBox = document.getElementById("suggestions");

    const text = customText || input.value.trim();
    if (!text) return;

    appendBubble("user", text);
    if (!customText) input.value = "";
    suggestBox.innerHTML = "";

    const loading = appendBubble("bot", "Đang tra cứu dữ liệu thực tế...");

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ msg: text, sid: SESSION_ID })
        });
        const data = await res.json();
        loading.remove();

        appendBubble("bot", data.reply);
        if (data.images) renderImages(data.images);
        if (data.suggestions) renderSuggestions(data.suggestions);
    } catch (e) {
        if (loading) loading.remove();
        appendBubble("bot", "⚠️ Lỗi kết nối. Hãy kiểm tra API Key trên Render Dashboard.");
    }
}

function appendBubble(role, text) {
    const container = document.getElementById("messages");
    const b = document.createElement("div");
    b.className = "bubble " + role;
    b.innerText = text;
    container.appendChild(b);
    container.scrollTop = container.scrollHeight;
    return b;
}

function renderImages(images) {
    const container = document.getElementById("messages");
    const row = document.createElement("div");
    row.className = "img-row";
    images.forEach(img => {
        const el = document.createElement("img");
        el.src = img.url;
        el.className = "img-item";
        el.onclick = () => {
            const modal = document.getElementById("img-modal");
            document.getElementById("img-modal-src").src = img.url;
            modal.style.display = "flex";
        };
        row.appendChild(el);
    });
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
}

function renderSuggestions(list) {
    const div = document.getElementById("suggestions");
    div.innerHTML = "";
    list.forEach(s => {
        const btn = document.createElement("button");
        btn.innerText = s;
        btn.onclick = () => sendMsg(s);
        div.appendChild(btn);
    });
}

// Map.js sẽ gọi hàm này
window.askChatbot = sendMsg;
window.sendMsg = sendMsg;

document.addEventListener("DOMContentLoaded", () => {
    // Đóng Modal ảnh
    document.addEventListener("click", (e) => {
        const modal = document.getElementById("img-modal");
        if (e.target.id === "img-close" || e.target === modal) {
            modal.style.display = "none";
        }
    });

    document.getElementById("send").onclick = () => sendMsg();
    document.getElementById("msg").onkeydown = (e) => { if(e.key === "Enter") sendMsg(); };

    // Xuất PDF
    document.getElementById("btn-export").onclick = async () => {
        const r = await fetch("/export-pdf", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ sid: SESSION_ID })
        });
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "Lich_trinh.pdf"; a.click();
    };

    // Xóa lịch sử
    document.getElementById("btn-clear").onclick = async () => {
        if (!confirm("Xóa hội thoại?")) return;
        await fetch("/clear", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ sid: SESSION_ID })
        });
        document.getElementById("messages").innerHTML = "";
    };
});
