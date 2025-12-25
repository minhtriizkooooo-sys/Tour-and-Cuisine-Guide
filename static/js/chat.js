// Biến lưu trữ Session ID tạm thời (sẽ mất khi F5 trang để đảm bảo không lưu lịch sử cũ)
const SESSION_ID = Math.random().toString(36).substring(7);

// ================= CHAT UI LOGIC =================
document.addEventListener("DOMContentLoaded", () => {
    const messagesEl = document.getElementById("messages");
    const msgInput = document.getElementById("msg");
    const sendBtn = document.getElementById("send");
    const suggestionsEl = document.getElementById("suggestions");

    const btnExport = document.getElementById("btn-export");
    const btnClear = document.getElementById("btn-clear");

    // Xóa sạch nội dung khi vừa load trang (Yêu cầu 1)
    messagesEl.innerHTML = "";
    suggestionsEl.innerHTML = "";

    /* ---------------- IMAGE MODAL (BUNG TO ẢNH) ---------------- */
    function openImageModal(src, caption) {
        let modal = document.getElementById("img-modal");
        if (!modal) {
            modal = document.createElement("div");
            modal.id = "img-modal";
            modal.style.cssText = `
                position:fixed; inset:0; background:rgba(0,0,0,0.9);
                display:none; align-items:center; justify-content:center;
                flex-direction:column; z-index:9999;
            `;
            modal.innerHTML = `
                <span id="img-close" style="position:absolute; top:20px; right:30px; color:white; font-size:40px; cursor:pointer;">&times;</span>
                <img id="img-modal-src" style="max-width:85%; max-height:80%; border-radius:8px; box-shadow:0 0 20px rgba(255,255,255,0.2);">
                <div id="img-modal-caption" style="color:white; margin-top:15px; font-size:18px; font-family:sans-serif;"></div>
            `;
            document.body.appendChild(modal);
            modal.querySelector("#img-close").onclick = () => modal.style.display = "none";
            modal.onclick = (e) => { if(e.target === modal) modal.style.display = "none"; };
        }
        document.getElementById("img-modal-src").src = src;
        document.getElementById("img-modal-caption").innerText = caption || "";
        modal.style.display = "flex";
    }

    /* ---------------- RENDER BUBBLE ---------------- */
    function appendBubble(role, text) {
        const b = document.createElement("div");
        b.className = "bubble " + (role === "user" ? "user" : "bot");
        b.innerText = text;
        messagesEl.appendChild(b);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return b;
    }

    /* ---------------- RENDER IMAGES ---------------- */
    function renderImages(images) {
        if (!images || !images.length) return;
        const row = document.createElement("div");
        row.className = "img-row";
        row.style.cssText = "display:flex; gap:10px; margin-top:5px; flex-wrap:wrap;";

        images.forEach(imgObj => {
            const src = typeof imgObj === "string" ? imgObj : imgObj.url;
            const caption = typeof imgObj === "string" ? "" : imgObj.caption;

            const img = document.createElement("img");
            img.src = src;
            img.className = "img-item"; // Sử dụng class từ style.css đã tạo
            img.style.cssText = "width:120px; height:85px; object-fit:cover; border-radius:8px; cursor:pointer; border:2px solid white; box-shadow:0 2px 5px rgba(0,0,0,0.2);";
            img.onclick = () => openImageModal(src, caption);
            row.appendChild(img);
        });

        messagesEl.appendChild(row);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    /* ---------------- RENDER VIDEOS ---------------- */
    function renderVideos(videos) {
        if (!videos || !videos.length) return;
        videos.forEach(link => {
            const a = document.createElement("a");
            a.href = link;
            a.target = "_blank";
            a.className = "video-link";
            a.innerHTML = "📺 Xem Video YouTube Liên Quan";
            messagesEl.appendChild(a);
        });
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    /* ---------------- RENDER SUGGESTIONS ---------------- */
    function renderSuggestions(list) {
        suggestionsEl.innerHTML = "";
        if (!list || !list.length) return;

        list.forEach(s => {
            const btn = document.createElement("button");
            btn.innerText = s;
            btn.onclick = () => {
                msgInput.value = s;
                sendMsg();
            };
            suggestionsEl.appendChild(btn);
        });
    }

    /* ---------------- SEND MESSAGE ---------------- */
    async function sendMsg(customText = null) {
        const text = customText || msgInput.value.trim();
        if (!text) return;

        appendBubble("user", text);
        if (!customText) msgInput.value = "";
        
        // Xóa suggestion cũ khi đang chờ trả lời mới
        suggestionsEl.innerHTML = "";

        const loading = appendBubble("bot", "Đang xử lý thông tin...");

        try {
            const r = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    msg: text,
                    sid: SESSION_ID // Gửi ID tạm thời để server nhận biết phiên làm việc
                })
            });

            const j = await r.json();
            loading.remove();

            // Hiển thị trả lời văn bản
            appendBubble("bot", j.reply || "Xin lỗi, tôi không tìm thấy thông tin này.");

            // Hiển thị Media & Suggestion theo ngữ cảnh (Yêu cầu thay đổi liên tục)
            if (j.images) renderImages(j.images);
            if (j.videos) renderVideos(j.videos);
            if (j.suggestions) renderSuggestions(j.suggestions);

        } catch (e) {
            loading.remove();
            appendBubble("bot", "❌ Lỗi kết nối hệ thống.");
            console.error(e);
        }
    }

    // Xuất hàm ra global để map.js có thể gọi được khi click vào bản đồ
    window.askChatbot = (question) => {
        sendMsg(question);
    };

    /* ---------------- EVENTS ---------------- */
    sendBtn.onclick = () => sendMsg();

    msgInput.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMsg();
        }
    };

    /* ---------------- EXPORT PDF ---------------- */
    btnExport.onclick = async () => {
        try {
            const resp = await fetch("/export-pdf", { 
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ sid: SESSION_ID })
            });
            if (!resp.ok) return alert("Không thể xuất PDF");
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `Lich_su_du_lich_${new Date().getTime()}.pdf`;
            a.click();
        } catch (e) { console.error(e); }
    };

    /* ---------------- CLEAR HISTORY (XÓA TOÀN BỘ) ---------------- */
    btnClear.onclick = async () => {
        if (!confirm("Bạn có chắc chắn muốn xóa vĩnh viễn lịch sử chat?")) return;
        await fetch("/clear-history", { 
            method: "POST", 
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sid: SESSION_ID })
        });
        messagesEl.innerHTML = "";
        suggestionsEl.innerHTML = "";
    };
});
