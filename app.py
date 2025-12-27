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
# Lấy Key từ Environment Variables trên Render
GEMINI_API_KEY = os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")
DB_PATH = "chat_history.db"
HOTLINE = "0908.08.3566"
BUILDER_NAME = "Vietnam Travel AI – Tours & Cuisine Guide - Lại Nguyễn Minh Trí"

# Khởi tạo Client
client = None
if GEMINI_API_KEY:
    try:
        # SDK google-genai bản mới nhất
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("--- Kết nối Gemini thành công ---")
    except Exception as e:
        print(f"--- Lỗi khởi tạo Gemini: {e} ---")

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

# ---------------- LOGIC AI (Đã sửa lỗi 404) ----------------
def call_gemini(user_msg):
    if not client: 
        return "Hệ thống chưa cấu hình API Key. Vui lòng kiểm tra lại biến môi trường trên Render."
    
    prompt = f"""
    Bạn là chuyên gia du lịch Việt Nam. Trả lời về: {user_msg}
    Yêu cầu:
    1. Nói về Lịch sử, Con người & Văn hóa, Ẩm thực.
    2. Nếu là tour: Chi tiết 4 ngày 3 đêm, chi phí ước tính.
    3. Đưa ra 3 câu hỏi gợi ý ở dòng cuối dạng: SUGGESTIONS: câu 1|câu 2|câu 3
    """
    
    # Danh sách các tên model để thử (tránh lỗi 404 NOT_FOUND)
    model_variants = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "models/gemini-1.5-flash"]
    
    last_error = ""
    for model_name in model_variants:
        try:
            response = client.models.generate_content(
                model=model_name, 
                contents=prompt
            )
            if response and response.text:
                return response.text
        except Exception as e:
            last_error = str(e)
            continue # Thử model tiếp theo nếu lỗi
            
    return f"Lỗi AI (404/Not Supported): {last_error}. Vui lòng kiểm tra lại vùng quốc gia của API Key hoặc cập nhật thư viện."

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    # Đảm bảo session_id luôn tồn tại
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    # Trả về file index.html nằm trong thư mục templates/
    resp = make_response(render_template("index.html", HOTLINE=HOTLINE, BUILDER=BUILDER_NAME))
    resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    msg = request.json.get("msg", "").strip()
    
    if not msg: 
        return jsonify({"text": "Bạn chưa nhập câu hỏi.", "suggestions": []})

    # Lưu lịch sử User
    db = get_db()
    db.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "user", msg, datetime.utcnow().isoformat()))
    
    # Gọi Gemini với cơ chế thử lại model
    full_reply = call_gemini(msg)
    
    # Tách xử lý Suggestions
    suggestions = ["Món ăn đặc sản", "Lịch sử địa danh", "Chi phí tham quan"]
    clean_reply = full_reply
    
    if "SUGGESTIONS:" in full_reply:
        parts = full_reply.split("SUGGESTIONS:")
        clean_reply = parts[0].strip()
        s_part = parts[1].strip()
        suggestions = [s.strip() for s in s_part.split("|")][:3]

    # Lưu lịch sử Bot
    db.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "bot", clean_reply, datetime.utcnow().isoformat()))
    db.commit()
    db.close()

    # Trả về JSON khớp với JavaScript data.text và data.suggestions
    return jsonify({
        "text": clean_reply,
        "suggestions": suggestions
    })

if __name__ == "__main__":
    # Render yêu cầu port 10000
    app.run(host="0.0.0.0", port=10000)
