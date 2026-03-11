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
app.secret_key = os.environ.get("SECRET_KEY", "tphcm_ai_travel_secret")
CORS(app)

# Cấu hình API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY_TCG")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# ================= PROMPT AI (Đã sửa để tránh lỗi 400) =================

SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch và quy hoạch đô thị TP.HCM. 
YÊU CẦU BẮT BUỘC: Trả về câu trả lời dưới định dạng JSON nguyên khối.

Chỉ trả lời địa danh thuộc TP.HCM.

Nếu địa danh KHÔNG thuộc TP.HCM, trả về JSON:
{
  "is_valid": false,
  "text": "Xin lỗi, hệ thống AI này chỉ hỗ trợ các địa danh thuộc phạm vi TP.HCM.",
  "suggestions": ["Quận 1 có gì chơi?", "Khu đô thị Thủ Thiêm", "Tuyến Metro số 1"]
}

Nếu địa danh HỢP LỆ, trả về JSON:
{
  "is_valid": true,
  "text": "Phân tích sâu về: 1. Lịch sử/Văn hóa. 2. Hiện trạng du lịch. 3. Tầm nhìn quy hoạch 2030-2045 (Metro, hạ tầng số, kinh tế đêm).",
  "suggestions": ["Lịch trình 1 ngày tại đây", "Giá vé và giờ mở cửa", "Các dự án hạ tầng sắp tới"]
}
"""

# ================= DATABASE =================

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
        """)

init_db()

# ================= SEARCH HELPERS =================

def search_serper(query, search_type="images", limit=8):
    if not SERPER_API_KEY:
        return []
    try:
        url = f"https://google.serper.dev/{search_type}"
        headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
        
        # Tối ưu query tìm kiếm
        if "future" in query:
            q = f"{query} Ho Chi Minh City 2030 vision development"
        else:
            q = f"{query} Ho Chi Minh City tourism"
            
        payload = json.dumps({"q": q})
        r = requests.post(url, headers=headers, data=payload)
        data = r.json()

        if search_type == "images":
            return [{"url": i["imageUrl"], "caption": i.get("title", "Hình ảnh")} for i in data.get("images", [])[:limit]]
        elif search_type == "videos":
            return [v["link"] for v in data.get("videos", [])[:3]]
    except Exception as e:
        print(f"Serper Error: {e}")
        return []

# ================= ROUTES =================

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
    if not msg:
        return jsonify({"error": "Nội dung trống"})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": msg}
            ],
            response_format={"type": "json_object"}
        )
        
        ai_res = json.loads(completion.choices[0].message.content)

        # Nếu địa danh hợp lệ, tiến hành tìm kiếm Media
        if ai_res.get("is_valid"):
            ai_res["images"] = search_serper(msg, "images", 8)
            ai_res["future_images"] = search_serper(f"quy hoạch {msg} tương lai", "images", 4)
            ai_res["future_youtube_links"] = search_serper(f"quy hoạch {msg}", "videos", 3)
        else:
            ai_res["images"] = []
            ai_res["future_images"] = []
            ai_res["future_youtube_links"] = []

        # Lưu lịch sử
        now = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id,role,content,created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, now))
            conn.execute("INSERT INTO messages (session_id,role,content,created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_res), now))

        return jsonify(ai_res)

    except Exception as e:
        return jsonify({
            "is_valid": False, 
            "text": f"Hệ thống gặp sự cố: {str(e)}",
            "images": [], "future_images": [], "future_youtube_links": []
        })

@app.route("/history")
def history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY id", (sid,))
        rows = cur.fetchall()

    res = []
    for r, c in rows:
        content = c
        if r == "bot":
            try: content = json.loads(c)
            except: pass
        res.append({"role": r, "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id", (sid,))
        rows = cur.fetchall()

    pdf = FPDF()
    pdf.add_page()
    
    # Cấu hình Font Tiếng Việt (Phải có file trong static/)
    font_added = False
    try:
        pdf.add_font("DejaVu", "", "static/DejaVuSans.ttf", uni=True)
        pdf.set_font("DejaVu", "", 11)
        font_added = True
    except:
        pdf.set_font("Arial", "", 11)

    pdf.cell(0, 10, "LỊCH SỬ TƯ VẤN DU LỊCH TPHCM", ln=True, align='C')
    pdf.ln(5)

    for role, content, time in rows:
        display_text = ""
        if role == "bot":
            try:
                data = json.loads(content)
                display_text = data.get("text", "")
            except:
                display_text = str(content)
        else:
            display_text = str(content)

        header = f"[{time}] {'NGƯỜI DÙNG' if role=='user' else 'AI CHUYÊN GIA'}:"
        pdf.set_text_color(200, 0, 0) if role == "user" else pdf.set_text_color(0, 100, 0)
        pdf.multi_cell(0, 8, header)
        
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 8, display_text)
        pdf.ln(3)
        pdf.cell(0, 0, "", "T") # Đường kẻ ngang
        pdf.ln(3)

    output_path = "/tmp/travel_history.pdf"
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
    return jsonify({"status": "đã xóa"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
