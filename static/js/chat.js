async function askChatbot(msg) {
    if (!msg.trim()) return;
    const chatBox = document.getElementById('chat-box');
    
    // 1. Hiển thị tin nhắn của bạn
    chatBox.innerHTML += `<div class="message user-msg" style="text-align:right; margin:10px; background:#e3f2fd; padding:10px; border-radius:10px;"><b>Bạn:</b> ${msg}</div>`;
    chatBox.scrollTop = chatBox.scrollHeight;

    // 2. Gọi API
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ msg: msg })
        });
        const data = await response.json();

        // 3. Xử lý gallery ảnh
        let imgHtml = '<div class="img-gallery" style="display:flex; overflow-x:auto; gap:10px; margin:10px 0;">';
        data.images.forEach(src => {
            imgHtml += `<img src="${src}" style="height:100px; border-radius:5px; cursor:pointer;" onclick="openImg('${src}')">`;
        });
        imgHtml += '</div>';

        // 4. Xử lý câu hỏi gợi ý
        let suggestHtml = '<div class="suggestions-area">';
        if (data.suggestions) {
            data.suggestions.forEach(q => {
                suggestHtml += `<button class="suggest-btn" onclick="askChatbot('${q}')">${q}</button>`;
            });
        }
        suggestHtml += '</div>';

        // 5. Hiển thị tin nhắn của AI
        chatBox.innerHTML += `
            <div class="message bot-msg" style="text-align:left; margin:10px; background:#f5f5f5; padding:10px; border-radius:10px; border-left:4px solid #2c3e50;">
                <b>AI:</b> <br>${data.text.replace(/\n/g, '<br>')}
                ${imgHtml}
                <br><a href="${data.youtube}" target="_blank" style="color:#d32f2f; font-weight:bold;">📺 Xem Video thực tế</a>
                ${suggestHtml}
            </div>
        `;
        chatBox.scrollTop = chatBox.scrollHeight;

    } catch (e) {
        chatBox.innerHTML += `<div style="color:red;">Lỗi kết nối server!</div>`;
    }
}

// Bắt sự kiện click nút gửi
document.getElementById('send-btn').onclick = () => {
    const input = document.getElementById('user-input');
    askChatbot(input.value);
    input.value = '';
};

// Bắt sự kiện phím Enter
document.getElementById('user-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') document.getElementById('send-btn').click();
});

function openImg(src) {
    document.getElementById('full-img').src = src;
    document.getElementById('overlay').style.display = 'flex';
}
