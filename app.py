import os
import uuid
import sqlite3
import json
import time
import random
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, Response
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = "trip_smart_2026_final_emergency" 
CORS(app)

# --- CẤU HÌNH API KEYS ---
API_KEYS = []
for key, value in os.environ.items():
    if "API_KEY" in key.upper() and value:
        parts = [k.strip() for k in value.split(',') if k.strip().startswith("AIza")]
        API_KEYS.extend(parts)

API_KEYS = list(set(API_KEYS))
# Nếu không có key nào trong biến môi trường, dùng danh sách rỗng để tránh crash
if not API_KEYS:
    print("[CRITICAL] Không tìm thấy API Key nào!")

# SỬ DỤNG MODEL 1.5-FLASH-8B VỚI VERSION ỔN ĐỊNH
model_id = "gemini-1.5-flash-8b" 
DB_PATH = "chat_history.db"

# Rút gọn System Instruction để tiết kiệm Token (giảm khả năng bị 429)
system_instruction = "Bạn là AI du lịch VN. Trả về JSON: {text: str, images: [{url, caption}], youtube_links: [str], suggestions: [str]}"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def get_ai_response(session_id, user_msg):
    if not API_KEYS:
        return {"text": "Lỗi: Hệ thống chưa có Key.", "images": [], "youtube_links": []}

    # CHỈ LẤY 2 CÂU HỘI THOẠI GẦN NHẤT (Cực kỳ quan trọng để tránh bị chặn IP)
    history_contents = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 2", (session_id,)).fetchall()
            for r in reversed(rows):
                role = "user" if r['role'] == 'user' else "model"
                txt = r['content']
                if role == "model":
                    try: txt = json.loads(txt).get('text', '...')
                    except: pass
                history_contents.append(types.Content(role=role, parts=[types.Part(text=txt)]))
    except: pass

    contents = history_contents + [types.Content(role="user", parts=[types.Part(text=user_msg)])]

    # Thử ngẫu nhiên 1 key, nếu lỗi thì dừng ngay để tránh bị Google khóa IP máy chủ
    selected_keys = random.sample(API_KEYS, min(len(API_KEYS), 5)) # Chỉ thử tối đa 5 key mỗi lần nhắn

    for key in selected_keys:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction, 
                    response_mime_type="application/json",
                    temperature=0.1 # Thấp nhất để xử lý nhanh nhất
                )
            )
            
            if response and response.text:
                return json.loads(response.text)
                
        except Exception as e:
            err = str(e)
            print(f"[DEBUG] Thử key thất bại, lỗi: {err[:30]}")
            # Nếu gặp 429, nghỉ lâu hơn một chút
            if "429" in err:
                time.sleep(3) 
            continue

    return {
        "text": "⚠️ Máy chủ Google đang tạm chặn kết nối từ Render. Hãy thử lại sau 2 phút hoặc đổi câu hỏi ngắn hơn.",
        "images": [], "youtube_links": [], "suggestions": ["Thử lại câu hỏi khác"]
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
    if not msg: return jsonify({"text": "..."})
    
    ai_data = get_ai_response(sid, msg) 
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, datetime.now().strftime("%H:%M")))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    except: pass
    return jsonify(ai_data)

# --- GIỮ CÁC ROUTE KHÁC (HISTORY, CLEAR...) ---
@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
            for r in rows:
                try: content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
                except: content = r['content']
                res.append({"role": r['role'], "content": content})
    except: pass
    return jsonify(res)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
