/**
 * VIETNAM TRAVEL AI - CHAT.JS (FULL VERSION)
 * Đã sửa: Modal đóng tuyệt đối, PDF Tiếng Việt, Scroll chống tràn, Tab Lịch sử
 */

const SESSION_ID = Math.random().toString(36).substring(7);

document.addEventListener("DOMContentLoaded", () => {
    // Khởi tạo các phần tử DOM
    const messagesEl = document.getElementById("messages");
    const msgInput = document.getElementById("msg");
    const sendBtn = document.getElementById("send");
    const suggestionsEl = document.getElementById("suggestions");
    const btnExport = document.getElementById("btn-export");
    const btnClear = document.getElementById("btn-clear");

    // Xóa sạch UI khi khởi động
    messagesEl.innerHTML = "";
    suggestionsEl.innerHTML = "";

    // ================= 1. XỬ LÝ MODAL ẢNH (BUNG TO & ĐÓNG X) =================
    
    // Hàm này được gắn vào window để các thẻ img được tạo động có thể gọi tới
    window.openImageModal = function(src, caption) {
        let modal = document.getElementById("img-modal");
        
        // Nếu modal chưa tồn tại trong HTML, ta tự tạo động
        if (!modal) {
            modal = document.createElement("div");
            modal.id = "img-modal";
            modal.className = "modal"; // Sử dụng class từ style.css
            modal.innerHTML = `
                <span id="img-close" class="modal-close">&times;</span>
                <img id="img-modal-src" class="modal-content">
                <div id="img-modal-caption" style="color:#ccc; margin-top:15px; font-size:18px;"></div>
            `;
            document.body.appendChild(modal);
        }

        const modalImg = document.getElementById("img-modal-src");
        const modalCap = document.getElementById("img-modal-caption");

        modalImg.src = src;
        modalCap.innerText = caption || "Hình ảnh minh họa du lịch";
        modal.style.display = "flex";
    };

    // Sự kiện đóng modal tuyệt đối khi click nút X hoặc vùng đen
    document.addEventListener("click", function(e) {
        const modal = document.getElementById("img-modal");
        if (!modal) return;
        if (e.target.id === "img-close" || e.target === modal) {
            modal.style.display = "none";
        }
    });

    // ================= 2. QUẢN LÝ TIN NHẮN (SCROLL & TRÀN) =================

    function appendBubble(role, text) {
        const b = document.createElement("div");
        b.className = "bubble " + (role === "user" ? "user" : "bot");
        b.innerText = text;
        
        // Thêm vào khung chat
        messagesEl.appendChild(b);
        
        // Yêu cầu: Tự động cuộn xuống tin nhắn mới nhất
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return b;
    }

    function renderImages(images) {
        if (!images || !images.length) return;
        const row = document.createElement("div");
        row.className = "img-row"; // Tận dụng CSS đã viết để không tràn
        
        images.forEach(imgObj => {
            const src = typeof imgObj === "string" ? imgObj : imgObj.url;
            const caption = typeof imgObj === "string" ? "" : imgObj.caption;

            const img = document.createElement("img");
            img.src = src;
            img.className = "img-item";
            img.loading = "lazy";
            img.onclick = () => window.openImageModal(src, caption);
            row.appendChild(img);
        });

        messagesEl.appendChild(row);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function renderSuggestions(list) {
        suggestionsEl.innerHTML = "";
        if (!list) return;
        list.forEach(s => {
            const btn = document.createElement("button");
            btn.innerText = s;
            btn.onclick = () => sendMsg(s);
            suggestionsEl.appendChild(btn);
        });
    }

    // ================= 3. LOGIC GỬI TIN & XỬ LÝ LỖI =================

    async function sendMsg(customText = null) {
        const text = customText || msgInput.value.trim();
        if (!text) return;

        // Hiện tin nhắn người dùng
        appendBubble("user", text);
        if (!customText) msgInput.value = "";
        
        // Xóa gợi ý cũ
        suggestionsEl.innerHTML = "";

        // Hiệu ứng chờ trả lời
        const loading = appendBubble("bot", "Hệ thống đang tìm kiếm dữ liệu...");

        try {
            const response = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ msg: text, sid: SESSION_ID })
            });

            if (!response.ok) throw new Error("Network Error");

            const data = await response.json();
            loading.remove();

            // Hiển thị câu trả lời (Yêu cầu: Không báo lỗi hệ thống bừa bãi)
            const finalReply = data.reply || `Cảm ơn bạn đã hỏi về ${text}. Đây là một thông tin du lịch thú vị.`;
            appendBubble("bot", finalReply);

            if (data.images) renderImages(data.images);
            if (data.suggestions) renderSuggestions(data.suggestions);

        } catch (error) {
            loading.remove();
            // Xử lý lỗi: Trả lời dự phòng thay vì hiện "Lỗi hệ thống"
            appendBubble("bot", `Về khu vực "${text}", tôi đang cập nhật thêm dữ liệu chi tiết. Bạn có muốn chỉ đường đến đó trên bản đồ không?`);
        }
    }

    // Gắn hàm vào window để map.js có thể gọi
    window.sendMsg = sendMsg;
    window.askChatbot = (q) => sendMsg(q);

    // ================= 4. TÍNH NĂNG NÂNG CAO (PDF, CLEAR, TABS) =================

    // Xuất PDF: Gửi yêu cầu xuống Python (app.py) để sinh file tiếng Việt
    btnExport.onclick = async function() {
        const notify = appendBubble("bot", "Đang xử lý xuất PDF tiếng Việt. Vui lòng đợi trong giây lát...");
        try {
            const res = await fetch("/export-pdf", { 
                method: "POST", 
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ sid: SESSION_ID }) 
            });
            notify.remove();
            
            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `Vietnam_Travel_Report.pdf`;
                a.click();
            }
        } catch (e) {
            notify.innerText = "❌ Hiện tại không thể xuất PDF. Hãy thử lại sau.";
        }
    };

    // Xóa lịch sử
    btnClear.onclick = function() {
        if (confirm("Bạn có chắc muốn xóa vĩnh viễn cuộc hội thoại này?")) {
            messagesEl.innerHTML = "";
            suggestionsEl.innerHTML = "";
            fetch("/clear-history", { 
                method: "POST", 
                headers: {"Content-Type": "application/json"}, 
                body: JSON.stringify({ sid: SESSION_ID }) 
            });
        }
    };

    // Tab Lịch sử
    window.viewHistory = function() {
        const count = messagesEl.querySelectorAll('.bubble.user').length;
        appendBubble("bot", `Bạn đã thực hiện ${count} lượt tra cứu địa danh trong phiên làm việc này.`);
    };

    // Sự kiện bàn phím
    sendBtn.onclick = () => sendMsg();
    msgInput.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMsg();
        }
    };
});
