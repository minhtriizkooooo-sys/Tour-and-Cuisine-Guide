import os
import uuid
import sqlite3
import json
import requests
from datetime import datetime
import pytz
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

# --- Cấu hình API ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY_TCG")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# --- Prompt AI (Đã tối ưu để tránh lỗi 400 và ép kiểu JSON) ---
SYSTEM_PROMPT = """Bạn là chuyên gia du lịch và quy hoạch đô thị CHỈ dành cho: TP.HCM, Vũng Tàu và Bình Dương.
NHIỆM VỤ: Trả về dữ liệu dưới định dạng JSON thuần túy.

1. Nếu địa danh KHÔNG thuộc 3 nơi này: 
   Trả JSON: {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ tư vấn du lịch và quy hoạch tại TP.HCM, Vũng Tàu và Bình Dương."}

2. Nếu địa danh HỢP LỆ:
   Cung cấp bài viết chi tiết (> 1800 từ) dùng Markdown (##, ###) bao gồm:
   - Lịch sử & Tầm nhìn tương lai 2030-2045.
   - Văn hóa, Con người và nhịp sống 2026.
   - Ẩm thực (Địa chỉ cụ thể + Giá cả 2026).
   - Lộ trình du lịch thông minh kết hợp các tuyến Metro/Hạ tầng mới.

Trả JSON mẫu:
{
  "is_valid": true,
  "text": "Nội dung bài viết dài ở đây...",
  "suggestions": ["Câu hỏi gợi ý 1", "Câu hỏi gợi ý 2", "Câu hỏi gợi ý 3"]
}"""

# --- Khởi tạo Database ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
        """)
init_db()

# --- Search Helpers (Ảnh & Video Hiện tại + Tương lai) ---
def search_media(query, type="images", future=False):
    if not SERPER_API_KEY: return []
    try:
        url = f"https://google.serper.dev/{type}"
        suffix = "quy hoạch tương lai dự án 2030" if future else "du lịch thực tế 2026"
        payload = json.dumps({"q": f"{query} {suffix}"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        
        if type == "images":
            return [{"url": i.get("imageUrl"), "caption": i.get("title")} for i in data.get("images", [])[:8]]
        else: # videos
            return [i.get("link") for i in data.get("videos", []) if "youtube" in i.get("link", "").lower()][:3]
    except:
        return []

# --- Routes ---
@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=31536000)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"error": "Nội dung trống"})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            response_format={"type": "json_object"}
        )
        ai_res = json.loads(completion.choices[0].message.content)

        if ai_res.get("is_valid"):
            # Lấy ảnh/video hiện tại
            ai_res["images"] = search_media(msg, "images", False)
            ai_res["youtube_links"] = search_media(msg, "videos", False)
            # Lấy ảnh/video tương lai
            ai_res["future_images"] = search_media(msg, "images", True)
            ai_res["future_youtube_links"] = search_media(msg, "videos", True)

        now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, now_vn))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_res), now_vn))

        return jsonify(ai_res)
    except Exception as e:
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "is_valid": False})

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()

    history = []
    for r, c in rows:
        try:
            content = json.loads(c) if r == "bot" else c
        except:
            content = c
        history.append({"role": r, "content": content})
    return jsonify(history)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()
    
    if not rows: return "Trống"

    pdf = FPDF()
    pdf.add_page()
    
    # Hỗ trợ tiếng Việt (Cần file DejaVuSans.ttf trong thư mục static)
    font_path = os.path.join("static", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=10)
    else:
        pdf.set_font("Arial", size=10)

    pdf.set_text_color(0, 51, 102)
    pdf.cell(200, 10, txt="CẨM NANG DU LỊCH & QUY HOẠCH 2026", ln=True, align='C')
    pdf.ln(10)

    for role, content, time in rows:
        pdf.set_text_color(150, 0, 0) if role == "user" else pdf.set_text_color(0, 100, 0)
        label = f"[{time}] NGƯỜI DÙNG: " if role == "user" else f"[{time}] CHUYÊN GIA AI: "
        
        text_to_print = content
        if role == "bot":
            try:
                data = json.loads(content)
                text_to_print = data.get("text", "")
            except: pass
        
        pdf.multi_cell(0, 8, txt=f"{label}\n{text_to_print}")
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    path = f"/tmp/history_{sid}.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
