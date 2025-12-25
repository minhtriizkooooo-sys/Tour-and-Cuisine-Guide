// ================= CHAT STATE =================
const chatBox = document.getElementById("chat-box");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("msg");
const clearBtn = document.getElementById("clear-chat");

let chatHistory = [];   // context hội thoại (RAM)
let placeContext = ""; // context địa điểm từ map

// ❌ KHÔNG load lại chat cũ khi reload
localStorage.removeItem("chatHistory");

// ================= UTILS =================
function scrollToBottom() {
  chatBox.scrollTop = chatBox.scrollHeight;
}

function escapeHTML(str) {
  return str.replace(/[&<>"']/g, m => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[m]));
}

// ================= MESSAGE RENDER =================
function renderUserMessage(text) {
  const div = document.createElement("div");
  div.className = "msg user";
  div.innerHTML = `<div class="bubble">${escapeHTML(text)}</div>`;
  chatBox.appendChild(div);
  scrollToBottom();
}

function renderBotMessage(content) {
  const div = document.createElement("div");
  div.className = "msg bot";

  div.innerHTML = `
    <div class="bubble">
      ${content.text || ""}
      ${renderImages(content.images)}
      ${renderVideos(content.videos)}
      ${renderSuggestions(content.suggestions)}
    </div>
  `;

  chatBox.appendChild(div);
  scrollToBottom();
}

// ================= RICH CONTENT =================
function renderImages(images = []) {
  if (!images.length) return "";

  return `
    <div class="chat-images">
      ${images.map(img => `
        <figure>
          <img src="${img.url}" alt="${img.caption}">
          <figcaption>${img.caption}</figcaption>
        </figure>
      `).join("")}
    </div>
  `;
}

function renderVideos(videos = []) {
  if (!videos.length) return "";

  return `
    <div class="chat-videos">
      ${videos.map(v => `
        <a href="${v.url}" target="_blank">🎬 ${v.title}</a>
      `).join("<br>")}
    </div>
  `;
}

function renderSuggestions(suggestions = []) {
  if (!suggestions.length) return "";

  return `
    <div class="chat-suggestions">
      ${suggestions.map(s => `
        <button onclick="sendSuggestion('${escapeHTML(s)}')">
          ${s}
        </button>
      `).join("")}
    </div>
  `;
}

// ================= SUGGESTION HANDLER =================
function sendSuggestion(text) {
  chatInput.value = text;
  chatForm.dispatchEvent(new Event("submit"));
}

// ================= CHATBOT CORE =================
async function askBot(question) {
  chatHistory.push({ role: "user", content: question });

  const payload = {
    question,
    history: chatHistory,
    place: placeContext
  };

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    chatHistory.push({ role: "assistant", content: data.text });

    renderBotMessage({
      text: `<p>${data.text}</p>`,
      images: data.images || [],
      videos: data.videos || [],
      suggestions: data.suggestions || []
    });

  } catch (err) {
    renderBotMessage({
      text: "❌ Có lỗi xảy ra khi kết nối chatbot."
    });
  }
}

// ================= FORM SUBMIT =================
chatForm.addEventListener("submit", e => {
  e.preventDefault();

  const text = chatInput.value.trim();
  if (!text) return;

  renderUserMessage(text);
  chatInput.value = "";

  askBot(text);
});

// ================= CLEAR CHAT =================
clearBtn.addEventListener("click", () => {
  chatBox.innerHTML = "";
  chatHistory = [];
  placeContext = "";

  localStorage.removeItem("chatHistory");
});

// ================= MAP → CHAT CONTEXT =================
// map.js sẽ gọi hàm này
window.setPlaceContext = function(place) {
  placeContext = place;
};

// ================= INIT GREETING =================
renderBotMessage({
  text: `
    <p><b>Xin chào 👋</b><br>
    Tôi là trợ lý du lịch thông minh.<br>
    Bạn có thể:
    <ul>
      <li>Click bản đồ để khám phá địa điểm</li>
      <li>Tìm đường và hỏi về vùng đi qua</li>
      <li>Hỏi về văn hóa, con người, ẩm thực</li>
    </ul>
    </p>
  `,
  suggestions: [
    "Gợi ý điểm du lịch nổi bật tại Việt Nam",
    "Ẩm thực đặc trưng miền Trung",
    "Lịch trình du lịch 3 ngày"
  ]
});
