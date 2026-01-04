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
app.secret_key = "trip_smart_pro_2026"
CORS(app)

# --- CẤU HÌNH GROQ ---
GROQ_KEYS = []
raw_keys = os.environ.get("GROQ_API_KEY", "")
if raw_keys:
    GROQ_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

DB_PATH = "chat_history.db"

# --- SYSTEM INSTRUCTION NÂNG CẤP ---
system_instruction = """
Bạn là một chuyên gia du lịch và văn hóa Việt Nam. Khi người dùng hỏi về một địa phương, bạn phải trả về JSON với nội dung cực kỳ chi tiết theo cấu trúc sau:

1. Lịch sử: Tóm tắt quá trình hình thành và phát triển.
2. Văn hóa & Con người: Đặc điểm tính cách, lễ hội, phong tục đặc sắc.
3. Ẩm thực: Các món ăn phải thử (kèm mô tả ngắn).
4. Gợi ý du lịch: Các địa danh nổi tiếng không nên bỏ qua.

BẮT BUỘC TRẢ VỀ JSON NGUYÊN BẢN:
{
  "text": "# [Tên địa phương]\\n## ⏳ Lịch sử hình thành\\n...\\n## 🎭 Văn hóa & Con người\\n...\\n## 🍲 Đặc sản ẩm thực\\n...\\n## 📍 Gợi ý điểm đến\\n...",
  "images": [
    {"url": "https://images.unsplash.com/featured/?{tên_địa_danh},vietnam", "caption": "Toàn cảnh điểm đến"},
    {"url": "https://images.unsplash.com/featured/?vietnam,food,{tên_món_ăn}", "caption": "Đặc sản địa phương"}
  ],
  "youtube_links": [
    "https://www.youtube.com/results?search_query=du+lich+{tên_địa_phương}"
  ],
  "suggestions": ["Món ăn nào ngon nhất ở đây?", "Lễ hội tiêu biểu là gì?"]
}
Lưu ý: Phần 'text' sử dụng Markdown để trình bày đẹp mắt (dùng #, ##, **).
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def get_ai_response(user_msg):
    if not GROQ_KEYS:
        return {"text": "Vui lòng cấu hình API Key.", "images": [], "suggestions": []}

    key = random.choice(GROQ_KEYS).strip()
    client = Groq(api_key=key)

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[
                {"role": "system", "content": "Return ONLY a valid JSON. " + system_instruction},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7,
            max_tokens=3000, # Tăng token để AI viết dài hơn
            response_format={"type": "json_object"}
        )
        
        return json.loads(completion.choices[0].message.content)
        
    except Exception as e:
        print(f"Error: {e}")
        return {"text": "Lỗi xử lý dữ liệu. Thử lại sau!", "images": [], "suggestions": []}

# --- ROUTES ---
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
    if not msg: return jsonify({"text": "Bạn muốn hỏi về đâu?"})

    ai_data = get_ai_response(msg)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    
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
                try: res.append({"role": "bot", "content": json.loads(r['content'])})
                except: res.append({"role": "bot", "content": {"text": r['content']}})
            else: res.append({"role": "user", "content": r['content']})
    return jsonify(res)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
