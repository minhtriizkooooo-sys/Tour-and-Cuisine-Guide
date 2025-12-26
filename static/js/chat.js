async function askChatbot(msg) {
    const chatBox = document.getElementById('chat-box');
    chatBox.innerHTML += `<div><b>Bạn:</b> ${msg}</div>`;

    const res = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({msg: msg})
    });
    const data = await res.json();

    let imgHtml = '<div class="img-gallery">';
    data.images.forEach((src, i) => {
        imgHtml += `<img src="${src}" onclick="openImg('${src}')">`;
    });
    imgHtml += '</div>';

    chatBox.innerHTML += `
        <div>
            <b>AI:</b> ${data.text.replace(/\n/g, '<br>')}
            ${imgHtml}
            <br><a href="${data.youtube}" target="_blank">Xem Video liên quan</a>
        </div>
    `;
}

function openImg(src) {
    document.getElementById('full-img').src = src;
    document.getElementById('overlay').style.display = 'flex';
}
function closeImg() { document.getElementById('overlay').style.display = 'none'; }

document.getElementById('user-input').addEventListener('keypress', (e) => {
    if(e.key === 'Enter') {
        askChatbot(e.target.value);
        e.target.value = '';
    }
});

let currentImages = [];
let currentImgIndex = 0;

function updateOverlayImg() {
    document.getElementById('full-img').src = currentImages[currentImgIndex];
}

window.openImg = (images, index) => {
    currentImages = images;
    currentImgIndex = index;
    updateOverlayImg();
    document.getElementById('overlay').style.display = 'flex';
};

window.nextImg = () => {
    currentImgIndex = (currentImgIndex + 1) % currentImages.length;
    updateOverlayImg();
};

window.prevImg = () => {
    currentImgIndex = (currentImgIndex - 1 + currentImages.length) % currentImages.length;
    updateOverlayImg();
};

// Hàm xử lý khi click vào câu hỏi gợi ý
async function handleSuggestion(text) {
    await askChatbot(text);
}

// Logic hiển thị tin nhắn có hình ảnh và nút gợi ý
function appendBotMessage(data) {
    const chatBox = document.getElementById('chat-box');
    let imgHtml = `<div class="img-gallery">`;
    data.images.forEach((src, i) => {
        imgHtml += `<img class="img-item" src="${src}" onclick="openImg(${JSON.stringify(data.images)}, ${i})">`;
    });
    imgHtml += `</div>`;

    // Giả sử AI trả về câu hỏi gợi ý ở cuối chuỗi bằng dấu [Suggest]
    let suggestionHtml = "";
    if(data.suggestions) {
        data.suggestions.forEach(s => {
            suggestionHtml += `<button class="tab-btn" style="margin:5px; font-size:0.8rem" onclick="handleSuggestion('${s}')">${s}</button>`;
        });
    }

    chatBox.innerHTML += `
        <div class="message bot-msg">
            ${data.text.replace(/\n/g, '<br>')}
            ${imgHtml}
            <p><a href="${data.youtube}" target="_blank">📺 Xem Video liên quan</a></p>
            <div class="suggestions-area">${suggestionHtml}</div>
        </div>
    `;
    chatBox.scrollTop = chatBox.scrollHeight;
}

