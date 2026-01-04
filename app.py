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
    GROQ_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

DB_PATH = "chat_history.db"

# System Instruction: Bắt buộc từ "JSON" phải có mặt để Groq không lỗi
system_instruction = """
Bạn là AI hướng dẫn du lịch Việt Nam chuyên nghiệp. 
BẮT BUỘC trả về dữ liệu dưới định dạng JSON sau:
{
  "text": "Nội dung Markdown tiếng Việt chi tiết (sử dụng **để bôi đậm).",
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
        return {"text": "Lỗi: Chưa cấu hình GROQ_API_KEY trên Render.", "images": [], "youtube_links": [], "suggestions": []}

    key = random.choice(GROQ_KEYS)
    client = Groq(api_key=key)

    try:
        completion = client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.6,
            max_tokens=2048,
            response_format={"type": "json_object"} # Chế độ JSON chuẩn của Groq
        )
        
        # Parse thử để đảm bảo là JSON hợp lệ
        res_content = completion.choices[0].message.content
        return json.loads(res_content)
        
    except Exception as e:
        print(f"[GROQ ERROR] {str(e)}")
        # Trả về JSON giả lập nhưng HỢP LỆ để không làm hỏng UI
        return {
            "text": "⚠️ Gemma đang bận xử lý hoặc hạn mức API đã hết. Bạn vui lòng đợi 10-15 giây rồi thử lại nhé!",
            "images": [],
            "youtube_links": [],
            "suggestions": ["Thử lại lần nữa", "Review địa điểm khác"]
        }

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    # Đảm bảo file index.html nằm trong thư mục templates
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=3600*24*7)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"text": "Hãy nhập nội dung cần hỏi."})

    ai_data = get_ai_response(msg)
    
    # Lưu vào DB - Lưu Bot dưới dạng String JSON
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, datetime.now().strftime("%H:%M")))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    except Exception as e:
        print(f"DB Error: {e}")
    
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
            for r in rows:
                if r['role'] == 'bot':
                    try:
                        # Quan trọng: Trả về Object JSON đã parse để UI nhận diện đúng
                        res.append({"role": "bot", "content": json.loads(r['content'])})
                    except:
                        res.append({"role": "bot", "content": {"text": r['content']}})
                else:
                    res.append({"role": "user", "content": r['content']})
    except Exception as e:
        print(f"History Error: {e}")
    return jsonify(res)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "deleted"})

if __name__ == "__main__":
    # Render yêu cầu dùng PORT từ biến môi trường
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
