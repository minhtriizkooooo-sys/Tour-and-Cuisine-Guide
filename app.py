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
GEMINI_API_KEY = os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")
DB_PATH = "chat_history.db"
HOTLINE = "0908.08.3566"
BUILDER_NAME = "Lại Nguyễn Minh Trí"

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Lỗi khởi tạo Gemini: {e}")

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
    if not client: return "Hệ thống chưa cấu hình API Key."
    prompt = f"Bạn là chuyên gia du lịch VN. Trả lời sâu về lịch sử, văn hóa, ẩm thực của: {user_msg}. Cuối cùng ghi: SUGGESTIONS: câu 1|câu 2|câu 3"
    
    # Thử các biến thể model để tránh lỗi 404
    for model_name in ["gemini-1.5-flash", "models/gemini-1.5-flash"]:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            return response.text
        except:
            continue
    return "AI hiện không phản hồi."

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html", HOTLINE=HOTLINE, BUILDER=BUILDER_NAME))
    resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"text": "Nội dung trống.", "suggestions": []})

    full_reply = call_gemini(msg)
    clean_reply = full_reply.split("SUGGESTIONS:")[0].strip()
    sugs = [s.strip() for s in full_reply.split("SUGGESTIONS:")[1].split("|")] if "SUGGESTIONS:" in full_reply else []

    return jsonify({"text": clean_reply, "suggestions": sugs[:3]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
