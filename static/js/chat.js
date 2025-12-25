// Biến lưu trữ Session ID tạm thời
const SESSION_ID = Math.random().toString(36).substring(7);

// ĐƯA HÀM RA NGOÀI ĐỂ MAP.JS CÓ THỂ GỌI ĐƯỢC
async function sendMsg(customText = null) {
    const messagesEl = document.getElementById("messages");
    const msgInput = document.getElementById("msg");
    const suggestionsEl = document.getElementById("suggestions");

    const text = customText || msgInput.value.trim();
    if (!text) return;

    // 1. Hiển thị tin nhắn người dùng
    appendBubble("user", text);
    if (!customText) msgInput.value = "";
    suggestionsEl.innerHTML = "";

    // 2. Hiệu ứng chờ trả lời thật (Không dùng fallback)
    const loading = appendBubble("bot", "Đang xử lý thông tin...");

    try {
        const r = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                msg: text,
                sid: SESSION_ID 
            })
        });

        const j = await r.json();
        loading.remove();

        // 3. Hiển thị nội dung từ OpenAI trả về
        if (j.reply) {
            appendBubble("bot", j.reply);
        } else {
            appendBubble("bot", "Xin lỗi, hệ thống không nhận được phản hồi.");
        }

        // Hiển thị Media & Suggestion
        if (j.images) renderImages(j.images);
        if (j.videos) renderVideos(j.videos);
        if (j.suggestions) renderSuggestions(j.suggestions);

    } catch (e) {
        if (loading) loading.remove();
        appendBubble("bot", "❌ Lỗi kết nối hệ thống. Vui lòng kiểm tra API Key.");
        console.error(e);
    }
}

// Các hàm bổ trợ (Helper Functions)
function appendBubble(role, text) {
    const messagesEl = document.getElementById("messages");
    const b = document.createElement("div");
    b.className = "bubble " + (role === "user" ? "user" : "bot");
    b.innerText = text;
    messagesEl.appendChild(b);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return b;
}

function renderImages(images) {
    const messagesEl = document.getElementById("messages");
    if (!images || !images.length) return;
    const row = document.createElement("div");
    row.className = "img-row";
    row.style.cssText = "display:flex; gap:10px; margin-top:5px; flex-wrap:wrap;";

    images.forEach(imgObj => {
        const src = typeof imgObj === "string" ? imgObj : imgObj.url;
        const caption = typeof imgObj === "string" ? "" : imgObj.caption;
        const img = document.createElement("img");
        img.src = src;
        img.className = "img-item";
        img.style.cssText = "width:120px; height:85px; object-fit:cover; border-radius:8px; cursor:pointer; border:2px solid white; box-shadow:0 2px 5px rgba(0,0,0,0.2);";
        img.onclick = () => openImageModal(src, caption);
        row.appendChild(img);
    });
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderVideos(videos) {
    const messagesEl = document.getElementById("messages");
    if (!videos || !videos.length) return;
    videos.forEach(link => {
        const a = document.createElement("a");
        a.href = link;
        a.target = "_blank";
        a.className = "video-link";
        a.innerHTML = "📺 Xem Video YouTube";
        messagesEl.appendChild(a);
    });
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderSuggestions(list) {
    const suggestionsEl = document.getElementById("suggestions");
    suggestionsEl.innerHTML = "";
    if (!list || !list.length) return;
    list.forEach(s => {
        const btn = document.createElement("button");
        btn.innerText = s;
        btn.onclick = () => sendMsg(s);
        suggestionsEl.appendChild(btn);
    });
}

function openImageModal(src, caption) {
    let modal = document.getElementById("img-modal");
    if (!modal) {
        modal = document.createElement("div");
        modal.id = "img-modal";
        modal.style.cssText = "position:fixed; inset:0; background:rgba(0,0,0,0.9); display:none; align-items:center; justify-content:center; flex-direction:column; z-index:9999;";
        modal.innerHTML = `
            <span id="img-close" style="position:absolute; top:20px; right:30px; color:white; font-size:40px; cursor:pointer;">&times;</span>
            <img id="img-modal-src" style="max-width:85%; max-height:80%; border-radius:8px;">
            <div id="img-modal-caption" style="color:white; margin-top:15px; font-size:18px;"></div>
        `;
        document.body.appendChild(modal);
        modal.querySelector("#img-close").onclick = () => modal.style.display = "none";
        modal.onclick = (e) => { if(e.target === modal) modal.style.display = "none"; };
    }
    document.getElementById("img-modal-src").src = src;
    document.getElementById("img-modal-caption").innerText = caption || "";
    modal.style.display = "flex";
}

// ĐĂNG KÝ CÁC BIẾN TOÀN CỤC ĐỂ MAP.JS TRUY CẬP
window.askChatbot = sendMsg;
window.sendMsg = sendMsg;

// ================= KHỞI TẠO EVENT =================
document.addEventListener("DOMContentLoaded", () => {
    const messagesEl = document.getElementById("messages");
    const msgInput = document.getElementById("msg");
    const sendBtn = document.getElementById("send");
    const suggestionsEl = document.getElementById("suggestions");
    const btnExport = document.getElementById("btn-export");
    const btnClear = document.getElementById("btn-clear");

    messagesEl.innerHTML = "";
    suggestionsEl.innerHTML = "";

    sendBtn.onclick = () => sendMsg();
    msgInput.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMsg();
        }
    };

    // EXPORT PDF
    btnExport.onclick = async () => {
        const resp = await fetch("/export-pdf", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sid: SESSION_ID })
        });
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Lich_su_du_lich.pdf`;
        a.click();
    };

    // CLEAR (Khớp với route /clear trong app.py)
    btnClear.onclick = async () => {
        if (!confirm("Xóa lịch sử?")) return;
        await fetch("/clear", { 
            method: "POST", 
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sid: SESSION_ID })
        });
        messagesEl.innerHTML = "";
        suggestionsEl.innerHTML = "";
    };
});
