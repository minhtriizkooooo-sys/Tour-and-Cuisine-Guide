// ================= CHAT.JS – FULL FIX =================
const messagesEl=document.getElementById("messages");
const suggestionsEl=document.getElementById("suggestions");
const inputEl=document.getElementById("msg");
const sendBtn=document.getElementById("send");
let chatHistory=[];

// ================= LOCAL STORAGE =================
function loadHistory(){ const data=localStorage.getItem("chatHistory"); if(data) chatHistory=JSON.parse(data); renderHistory(); }
function saveHistory(){ localStorage.setItem("chatHistory",JSON.stringify(chatHistory)); }
function clearHistory(){ chatHistory=[]; localStorage.removeItem("chatHistory"); renderHistory(); }

// ================= RENDER =================
function renderHistory(){ messagesEl.innerHTML=""; chatHistory.forEach(msg=>{ appendMessage(msg.role,msg.content,msg.media); }); }

// ================= APPEND MESSAGE =================
function appendMessage(role,text,media=[]){
  const bubble=document.createElement("div");
  bubble.className=`bubble ${role}`;
  bubble.innerHTML=text.replace(/\n/g,"<br>");
  media.forEach(m=>{
    if(m.type==="image"){ const img=document.createElement("img"); img.src=m.src; img.alt=m.caption||""; img.style.cursor="pointer"; img.style.maxWidth="90%"; img.style.marginTop="6px"; img.onclick=()=>openImageModal(m.src,m.caption); bubble.appendChild(img); if(m.caption){ const cap=document.createElement("div"); cap.style.fontSize="12px"; cap.style.color="#555"; cap.style.marginBottom="4px"; cap.innerText=m.caption; bubble.appendChild(cap); } }
    else if(m.type==="video"){ const vid=document.createElement("iframe"); vid.src=m.src; vid.width="100%"; vid.height="200px"; vid.style.marginTop="6px"; bubble.appendChild(vid); }
  });
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop=messagesEl.scrollHeight;
}

// ================= SEND =================
sendBtn.addEventListener("click",()=>{
  const text=inputEl.value.trim();
  if(!text) return;
  appendMessage("user",text);
  chatHistory.push({role:"user",content:text});
  inputEl.value="";
  generateBotResponse(text);
});

// ================= BOT RESPONSE =================
function generateBotResponse(userText){
  setTimeout(()=>{
    const response=`Chatbot trả lời cho: "${userText}"\nGiới thiệu văn hóa, lịch sử, con người, ẩm thực tại địa điểm này.`;
    const media=[{type:"image",src:"/static/images/sample1.jpg",caption:"Ẩm thực đặc trưng"},{type:"video",src:"https://www.youtube.com/embed/dQw4w9WgXcQ"}];
    appendMessage("bot",response,media);
    chatHistory.push({role:"bot",content:response,media});
    saveHistory();
    updateSuggestions(userText);
  },600);
}

// ================= SUGGESTIONS =================
function updateSuggestions(prevText){
  suggestionsEl.innerHTML="";
  const suggestions=[
    `Khám phá thêm địa điểm gần ${prevText}`,
    `Ẩm thực nổi bật tại ${prevText}`,
    `Lịch sử và văn hóa tại ${prevText}`,
    `Gợi ý tour du lịch 1 ngày quanh ${prevText}`
  ];
  suggestions.forEach(s=>{
    const btn=document.createElement("button");
    btn.innerText=s;
    btn.onclick=()=>{ inputEl.value=s; sendBtn.click(); };
    suggestionsEl.appendChild(btn);
  });
}

// ================= CHAT TABS =================
document.getElementById("btn-clear").addEventListener("click",clearHistory);
document.getElementById("btn-history").addEventListener("click",()=>{ renderHistory(); });
document.getElementById("btn-export").addEventListener("click",()=>{ exportPDF(); });

// ================= EXPORT PDF =================
function exportPDF(){
  const pdf=new jsPDF();
  let y=10;
  chatHistory.forEach(msg=>{
    const lines=pdf.splitTextToSize(msg.content,180);
    pdf.setFont(msg.role==="user"?"helvetica":"times");
    pdf.setFontSize(12);
    pdf.text(lines,10,y);
    y+=lines.length*7+4;
    if(msg.media) y+=msg.media.length*10;
    if(y>270){ pdf.addPage(); y=10; }
  });
  pdf.save("chat_history.pdf");
}

// ================= INIT =================
loadHistory();
