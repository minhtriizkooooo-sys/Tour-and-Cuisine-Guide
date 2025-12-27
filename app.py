import os
import io
import uuid
import sqlite3
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template,
    make_response, send_file
)
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
GEMINI_API_KEY = os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")
DB_PATH = "chat_history.db"
HOTLINE = "0908.08.3566"
BUILDER_NAME = "Vietnam Travel AI – Tours & Cuisine Guide - Lại Nguyễn Minh Trí"

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Lỗi khởi tạo Gemini: {e}")

# ---------------- DATABASE ----------------
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

# ---------------- LOGIC AI ----------------
def call_gemini(user_msg):
    if not client: return "Hệ thống chưa cấu hình API Key."
    
    prompt = f"""
    Bạn là chuyên gia du lịch Việt Nam. Trả lời về: {user_msg}
    Yêu cầu:
    1. Nói về Lịch sử, Con người & Văn hóa, Ẩm thực.
    2. Nếu là tour: Chi tiết 4 ngày 3 đêm, chi phí ước tính.
    3. Đưa ra 3 câu hỏi gợi ý ở dòng cuối dạng: SUGGESTIONS: câu 1|câu 2|câu 3
    """
    try:
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"Lỗi kết nối AI: {str(e)}"

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    # SỬA TẠI ĐÂY: Dùng "index.html" thay vì "ui.html" để tránh lỗi 500
    resp = make_response(render_template("index.html", HOTLINE=HOTLINE, BUILDER=BUILDER_NAME))
    resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"text": "Nội dung trống.", "suggestions": []})

    db = get_db()
    db.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "user", msg, datetime.utcnow().isoformat()))
    
    full_reply = call_gemini(msg)
    
    # Tách Suggestions
    suggestions = ["Đặc sản địa phương", "Lịch sử vùng này", "Chi phí du lịch"]
    if "SUGGESTIONS:" in full_reply:
        parts = full_reply.split("SUGGESTIONS:")
        clean_reply = parts[0].strip()
        suggestions = [s.strip() for s in parts[1].split("|")][:3]
    else:
        clean_reply = full_reply

    db.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "bot", clean_reply, datetime.utcnow().isoformat()))
    db.commit()
    db.close()

    # SỬA TẠI ĐÂY: Trả về "text" để khớp với JavaScript (data.text)
    return jsonify({
        "text": clean_reply,
        "suggestions": suggestions
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
