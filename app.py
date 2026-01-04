import os
import uuid
import sqlite3
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
from groq import Groq
import random

app = Flask(__name__)
app.secret_key = "trip_smart_gemma_2026"
CORS(app)

# --- CẤU HÌNH GROQ API KEYS ---
GROQ_KEYS = []
raw_keys = os.environ.get("GROQ_API_KEY", "")
if raw_keys:
    # Làm sạch key để tránh lỗi khoảng trắng
    GROQ_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

DB_PATH = "chat_history.db"

# System Instruction: Ép kiểu JSON và sử dụng model mới
system_instruction = """
Bạn là AI hướng dẫn du lịch Việt Nam chuyên nghiệp. 
BẮT BUỘC trả về dữ liệu định dạng JSON nguyên bản.
{
  "text": "Nội dung Markdown tiếng Việt (dùng ** để bôi đậm các địa danh).",
  "images": [{"url": "https://images.unsplash.com/featured/?vietnam,{keyword}", "caption": "Ảnh minh họa"}],
  "youtube_links": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
  "suggestions": ["Bạn muốn đi đâu tiếp theo?", "Hỏi về món ăn tại đây"]
}
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def get_ai_response(user_msg):
    if not GROQ_KEYS:
        return {"text": "Lỗi: Chưa có API Key.", "images": [], "suggestions": []}

    key = random.choice(GROQ_KEYS).strip()
    client = Groq(api_key=key)

    try:
        # ĐÃ SỬA: Thay thế gemma2-9b-it bằng llama-3.3-70b-versatile
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[
                {"role": "system", "content": "You must respond in JSON format. " + system_instruction},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        
        res_content = completion.choices[0].message.content
        return json.loads(res_content)
        
    except Exception as e:
        print(f"[ERROR] Chi tiết lỗi: {str(e)}")
        # Trả về JSON dự phòng để không hỏng UI
        return {
            "text": "⚠️ Hệ thống đang bảo trì model. Vui lòng thử lại sau vài giây!",
            "images": [],
            "youtube_links": [],
            "suggestions": ["Thử lại"]
        }

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=3600*24*7)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"text": "Nhập tin nhắn..."})

    ai_data = get_ai_response(msg)
    
    # Lưu vào DB
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, datetime.now().strftime("%H:%M")))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    except: pass
    
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        for r in rows:
            if r['role'] == 'bot':
                try:
                    res.append({"role": "bot", "content": json.loads(r['content'])})
                except:
                    res.append({"role": "bot", "content": {"text": r['content']}})
            else:
                res.append({"role": "user", "content": r['content']})
    return jsonify(res)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
