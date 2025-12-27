import os
import uuid
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
# Chỗ này lấy Key từ Render Environment. Đảm bảo bro đã đặt tên là GEMINI_KEY
API_KEY = os.environ.get("GEMINI_KEY") or os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")
DB_PATH = "chat_history.db"

client = None
if API_KEY:
    try:
        client = genai.Client(api_key=API_KEY)
        print("--- KET NOI GEMINI THANH CONG ---")
    except Exception as e:
        print(f"--- LOI KHOI TAO CLIENT: {e} ---")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
    db.commit()
    db.close()

init_db()

def call_gemini(user_msg):
    if not client:
        return "Lỗi: Chưa tìm thấy API Key trên Render. Bro hãy kiểm tra Environment Variables."
    
    prompt = f"Bạn là chuyên gia du lịch Việt Nam. Hãy kể sâu về lịch sử, văn hóa và ẩm thực của: {user_msg}. Cuối câu trả lời luôn có dòng: SUGGESTIONS: câu 1|câu 2|câu 3"
    
    # Danh sách các model để chạy thử, tránh 404
    models_to_try = ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-1.5-flash-latest"]
    
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Thử model {model_name} thất bại: {e}")
            continue
            
    return "AI hiện tại không phản hồi. Có thể do giới hạn vùng (Region) hoặc API Key hết hạn."

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    # Đảm bảo index.html nằm trong thư mục templates
    resp = make_response(render_template("index.html", HOTLINE="0908.08.3566", BUILDER="Lại Nguyễn Minh Trí"))
    resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    data = request.json
    msg = data.get("msg", "").strip()
    
    if not msg:
        return jsonify({"text": "Bro chưa nhập gì cả!", "suggestions": []})

    full_reply = call_gemini(msg)
    
    # Tách tin nhắn và gợi ý
    clean_reply = full_reply
    suggestions = ["Món ăn ngon", "Lịch sử vùng này", "Giá vé tham quan"]
    
    if "SUGGESTIONS:" in full_reply:
        parts = full_reply.split("SUGGESTIONS:")
        clean_reply = parts[0].strip()
        suggestions = [s.strip() for s in parts[1].split("|")][:3]

    return jsonify({
        "text": clean_reply,
        "suggestions": suggestions
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
