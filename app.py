import os
import io
import uuid
import sqlite3
import requests
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template,
    make_response, send_file
)
from flask_cors import CORS
from google import genai  # Thư viện mới nhất của bạn

# PDF (Unicode)
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
# Lấy Key Gemini thay vì OpenAI
GEMINI_API_KEY = os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")
DB_PATH = "chat_history.db"
HOTLINE = "0908.08.3566"
BUILDER_NAME = "Vietnam Travel AI – Lại Nguyễn Minh Trí"

# Khởi tạo Client Gemini
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------- DATABASE (Giữ nguyên của bạn) ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS suggestions (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, question TEXT, created_at TEXT)")
    db.commit()
    db.close()

init_db()

# ---------------- LOGIC AI (Gemini thay thế OpenAI) ----------------
def call_gemini(user_msg):
    if not client: return "Lỗi: Chưa cấu hình API Key."
    
    prompt = f"""
    Bạn là chuyên gia du lịch Việt Nam. Trả lời về: {user_msg}
    Yêu cầu:
    1. Nói về Lịch sử, Con người & Văn hóa, Ẩm thực.
    2. Nếu là tour: Chi tiết 4 ngày 3 đêm, chi phí ước tính.
    3. Đưa ra từ khóa hình ảnh tiếng Anh ở dòng cuối dạng: KEYWORD: [từ khóa]
    4. Gợi ý 3 câu hỏi tiếp theo ở dòng cuối dạng: SUGGESTIONS: câu 1|câu 2|câu 3
    """
    
    try:
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"Lỗi AI: {str(e)}"

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("ui.html", HOTLINE=HOTLINE, BUILDER=BUILDER_NAME))
    resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"error": "empty"}), 400

    # Lưu lịch sử vào DB
    db = get_db()
    db.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "user", msg, datetime.utcnow().isoformat()))
    
    # Gọi Gemini
    full_reply = call_gemini(msg)
    
    # Tách lấy Keyword và Suggestions từ text của Gemini
    keyword = "vietnam travel"
    if "KEYWORD:" in full_reply:
        keyword = full_reply.split("KEYWORD:")[-1].split("\n")[0].strip()
    
    suggestions = []
    if "SUGGESTIONS:" in full_reply:
        s_part = full_reply.split("SUGGESTIONS:")[-1].strip()
        suggestions = [s.strip() for s in s_part.split("|")]

    # Lưu Bot reply vào DB
    clean_reply = full_reply.split("KEYWORD:")[0].strip()
    db.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "bot", clean_reply, datetime.utcnow().isoformat()))
    
    # Lưu suggestions
    for s in suggestions:
        db.execute("INSERT INTO suggestions (session_id, question, created_at) VALUES (?,?,?)",
                   (sid, s, datetime.utcnow().isoformat()))
    db.commit()
    db.close()

    # Giả lập tìm kiếm ảnh/video bằng keyword từ AI (Thay thế SerpApi đã hết hạn)
    images = [{"url": f"https://loremflickr.com/400/300/{keyword}", "caption": keyword}]
    videos = [f"https://www.youtube.com/results?search_query={keyword}+travel+guide"]

    return jsonify({
        "reply": clean_reply,
        "images": images,
        "videos": videos,
        "suggestions": suggestions
    })

@app.route("/history")
def history():
    sid = request.cookies.get("session_id")
    db = get_db()
    rows = db.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY id", (sid,)).fetchall()
    db.close()
    return jsonify({"history": [dict(r) for r in rows]})

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    # Giữ nguyên logic ReportLab của bạn
    # Lưu ý: Bạn cần file font DejaVuSans.ttf trong thư mục static để không lỗi tiếng Việt
    sid = request.cookies.get("session_id")
    db = get_db()
    history = db.execute("SELECT role, content FROM messages WHERE session_id=?", (sid,)).fetchall()
    db.close()

    buffer = io.BytesIO()
    # (Đoạn này giữ nguyên các bước tạo PDF bằng reportlab như code cũ của bạn)
    # ... code logic reportlab ...
    return send_file(buffer, as_attachment=True, download_name="history.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
