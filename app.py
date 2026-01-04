import os
import uuid
import sqlite3
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
from groq import Groq  # Thư viện mới để dùng Gemma
import random

app = Flask(__name__)
app.secret_key = "trip_smart_gemma_2026"
CORS(app)

# --- CẤU HÌNH GROQ API KEYS ---
GROQ_KEYS = []
raw_keys = os.environ.get("GROQ_API_KEY", "")
if raw_keys:
    GROQ_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

DB_PATH = "chat_history.db"

# System Instruction cho Gemma 2 (Cần ghi rõ hơn để ép trả về JSON chuẩn)
system_instruction = """
Bạn là AI hướng dẫn du lịch Việt Nam chuyên nghiệp. 
BẮT BUỘC trả về dữ liệu dưới dạng JSON nguyên bản, không nằm trong tag ```json```:
{
  "text": "Nội dung Markdown tiếng Việt chi tiết.",
  "images": [{"url": "https://images.unsplash.com/featured/?{keyword},vietnam", "caption": "Mô tả ảnh"}],
  "youtube_links": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
  "suggestions": ["Câu hỏi gợi ý 1", "Câu hỏi gợi ý 2"]
}
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def get_ai_response(user_msg):
    if not GROQ_KEYS:
        return {"text": "Lỗi: Chưa cấu hình GROQ_API_KEY.", "images": [], "youtube_links": []}

    # Chọn ngẫu nhiên 1 Key Groq
    key = random.choice(GROQ_KEYS)
    client = Groq(api_key=key)

    try:
        # Gọi mô hình Gemma 2 9B (Rất mạnh và hỗ trợ tiếng Việt khá tốt)
        completion = client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.5,
            max_tokens=2048,
            # Chế độ JSON cực kỳ ổn định trên Groq
            response_format={"type": "json_object"}
        )
        
        return json.loads(completion.choices[0].message.content)
        
    except Exception as e:
        print(f"[GROQ ERROR] {str(e)}")
        return {
            "text": "⚠️ Gemma đang bận xử lý. Vui lòng thử lại sau giây lát.",
            "images": [],
            "youtube_links": [],
            "suggestions": ["Thử lại"]
        }

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"text": "Hãy nhập tin nhắn."})

    ai_data = get_ai_response(msg)
    
    # Lưu vào DB
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    
    return jsonify(ai_data)

# Route lấy lịch sử để hiển thị lại khi F5
@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        for r in rows:
            try:
                content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
            except:
                content = r['content']
            res.append({"role": r['role'], "content": content})
    return jsonify(res)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
