// Mảng lưu trữ lịch sử cuộc gọi
let chatHistory = [];

async function askChatbot(msg) {
    if (!msg.trim()) return;
    
    // Lưu vào lịch sử nếu là câu hỏi mới
    if (!chatHistory.includes(msg)) {
        chatHistory.unshift(msg); // Thêm vào đầu mảng
        updateHistoryUI();
    }

    const chatBox = document.getElementById('chat-box');
    
    // Hiển thị tin nhắn người dùng
    chatBox.innerHTML += `
        <div class="message user-msg">
            <b>Bạn:</b> ${msg}
        </div>`;
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ msg: msg })
        });
        const data = await response.json();

        // Tạo Gallery ảnh
        let imgHtml = '<div class="img-gallery">';
        data.images.forEach(src => {
            imgHtml += `<img src="${src}" class="img-item" onclick="openImg('${src}')">`;
        });
        imgHtml += '</div>';

        // Tạo câu hỏi gợi ý
        let suggestHtml = '<div style="margin-top:10px; display:flex; gap:5px; flex-wrap:wrap;">';
        data.suggestions.forEach(s => {
            suggestHtml += `<button class="tab-btn" style="font-size:0.75rem; border:1px solid #0077b6; border-radius:15px; padding:3px 10px;" onclick="askChatbot('${s}')">${s}</button>`;
        });
        suggestHtml += '</div>';

        // Hiển thị tin nhắn AI
        chatBox.innerHTML += `
            <div class="message bot-msg">
                <b>AI:</b> <br>${data.text.replace(/\n/g, '<br>')}
                ${imgHtml}
                ${data.youtube ? `<br><a href="${data.youtube}" target="_blank" style="color:#d00; font-weight:bold;">📺 Xem Video thực tế</a>` : ''}
                ${suggestHtml}
            </div>
        `;
        chatBox.scrollTop = chatBox.scrollHeight;

    } catch (e) {
        chatBox.innerHTML += `<div style="color:red; padding:10px;">Lỗi kết nối server!</div>`;
    }
}

// Cập nhật giao diện danh sách lịch sử
function updateHistoryUI() {
    const historyList = document.getElementById('history-list');
    if (!historyList) return;

    historyList.innerHTML = chatHistory.map(item => `
        <div class="history-item" onclick="loadHistoryItem('${item}')">
            📍 ${item.substring(0, 30)}${item.length > 30 ? '...' : ''}
        </div>
    `).join('');
}

// Khi nhấn vào một mục trong lịch sử
function loadHistoryItem(msg) {
    showTab('chat'); // Quay lại tab hội thoại
    document.getElementById('user-input').value = msg;
    askChatbot(msg);
}

// Xử lý nút Gửi
document.getElementById('send-btn').onclick = () => {
    const input = document.getElementById('user-input');
    askChatbot(input.value);
    input.value = '';
};

// Xử lý phím Enter
document.getElementById('user-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') document.getElementById('send-btn').click();
});

// Xem ảnh phóng to
function openImg(src) {
    document.getElementById('full-img').src = src;
    document.getElementById('overlay').style.display = 'flex';
}

function exportPDF() {
    const chatBox = document.getElementById('chat-box');
    
    // Kiểm tra xem có nội dung để xuất không
    if (chatBox.innerText.trim() === "" || chatBox.innerText.includes("Xin chào!")) {
        alert("Chưa có nội dung hội thoại để xuất PDF!");
        return;
    }

    // Cấu hình định dạng PDF
    const opt = {
        margin:       10,
        filename:     'lich-trinh-du-lich-vietnam.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    // Chạy lệnh xuất PDF từ nội dung chat-box
    html2pdf().set(opt).from(chatBox).save();
}

// Hàm hiển thị trạng thái đang xử lý
function showLoading(status) {
    const overlay = document.getElementById('loading-overlay');
    overlay.style.display = status ? 'flex' : 'none';
}

// CẬP NHẬT HÀM ASKCHATBOT
async function askChatbot(msg) {
    if (!msg.trim()) return;
    
    showLoading(true); // <--- BẮT ĐẦU HIỆN "ĐANG XỬ LÝ"

    // (Các code lưu lịch sử giữ nguyên...)

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ msg: msg })
        });
        const data = await response.json();
        
        // (Code hiển thị tin nhắn AI giữ nguyên...)

    } catch (e) {
        // Xử lý lỗi
    } finally {
        showLoading(false); // <--- TẮT "ĐANG XỬ LÝ" SAU KHI XONG
    }
}

// CẬP NHẬT HÀM TÌM KIẾM BẢN ĐỒ (Trong map.js hoặc chat.js)
async function searchLocation() {
    const query = document.getElementById('map-search-input').value;
    if(!query) return;

    showLoading(true); // <--- HIỆN KHI ĐANG TÌM ĐỊA DANH

    try {
        const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${query}`);
        const data = await res.json();
        // (Xử lý bản đồ giữ nguyên...)
        
        // Sau đó gọi chatbot
        await askChatbot(`Kể cho tôi về ${query}`);
    } catch (e) {
        console.error(e);
    } finally {
        showLoading(false); // <--- TẮT KHI ĐÃ XONG
    }
}

function exportPDF() {
    showLoading(true);
    const chatBox = document.getElementById('chat-box');
    
    const opt = { /* ...cấu hình giữ nguyên... */ };

    html2pdf().set(opt).from(chatBox).save().then(() => {
        showLoading(false); // Tắt khi file đã tải xuống
    });
}

