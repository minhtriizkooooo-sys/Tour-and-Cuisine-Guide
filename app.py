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

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY_TCG")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Cập nhật Prompt để AI linh hoạt hơn với các địa danh thuộc TP.HCM, Vũng Tàu, Bình Dương
SYSTEM_PROMPT = """Bạn là chuyên gia du lịch am hiểu sâu sắc về TP.HCM, Vũng Tàu và Bình Dương.
NHIỆM VỤ:
1. Kiểm tra địa danh: Nếu thuộc TP.HCM (kể cả các quận, huyện, đường phố cụ thể), Vũng Tàu hoặc Bình Dương -> Proceed.
2. Nếu hoàn toàn KHÔNG thuộc 3 khu vực này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi hiện chỉ hỗ trợ thông tin du lịch chuyên sâu tại TP.HCM, Vũng Tàu và Bình Dương."}
3. Nếu HỢP LỆ: Trả về bài viết cực kỳ chi tiết (> 1800 từ), sử dụng Markdown (##, ###, bullet points).
   Cấu trúc bắt buộc trong trường "text":
   - Lịch sử & Sự tích địa danh (từ quá khứ đến hiện tại).
   - Tầm nhìn phát triển 2026: Các dự án hạ tầng, metro, hoặc quy hoạch mới tại khu vực đó.
   - Văn hóa, lối sống và con người địa phương.
   - Ẩm thực: Danh sách món ăn + Địa chỉ cụ thể + Giá dự kiến năm 2026.
   - Lộ trình tham quan chi tiết từ 1-3 ngày.

Trả về định dạng JSON thuần túy:
{
  "is_valid": true,
  "text": "nội dung bài viết dài...",
  "suggestions": ["Câu hỏi gợi ý 1", "Câu hỏi gợi ý 2", "Câu hỏi gợi ý 3"]
}"""

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

# --- Helper Functions ---
def search_serper_images(query):
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": f"du lịch {query} thực tế 2026 đẹp nhất"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        return [{"url": i.get("imageUrl"), "caption": i.get("title", query)} for i in data.get("images", [])[:8]]
    except: return []

def search_serper_youtube(query):
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/videos"
        payload = json.dumps({"q": f"review du lịch {query} 2026 mới nhất"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        return [i.get("link") for i in resp.json().get("videos", []) if "youtube" in i.get("link", "").lower()] [:3]
    except: return []

def search_serper_future_images(query):
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/images"
        # Query tập trung vào quy hoạch và dự án 2026
        payload = json.dumps({"q": f"quy hoạch hạ tầng {query} 2026 2030 dự án tương lai"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        return [{"url": i.get("imageUrl"), "caption": i.get("title", "Tầm nhìn tương lai")} for i in data.get("images", [])[:4]]
    except: return []

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
    if not msg: return jsonify({"error": "Empty message"})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            response_format={"type": "json_object"}
        )
        ai_res = json.loads(completion.choices[0].message.content)

        if ai_res.get("is_valid"):
            ai_res["images"] = search_serper_images(msg)
            ai_res["youtube_links"] = search_serper_youtube(msg)
            # Lấy thêm ảnh tương lai dựa trên query người dùng
            ai_res["future_images"] = search_serper_future_images(msg)

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

    formatted_history = []
    for r, c in rows:
        try:
            content = json.loads(c) if r == "bot" else c
        except:
            content = c
        formatted_history.append({"role": r, "content": content})
    return jsonify(formatted_history)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()
    if not rows: return "Không có dữ liệu."

    pdf = FPDF()
    pdf.add_page()
    
    # Cần đảm bảo file DejaVuSans.ttf nằm trong folder static/
    font_path = os.path.join("static", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=11)
    else:
        pdf.set_font("Arial", size=11)

    now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    pdf.cell(0, 10, txt="CAM NANG DU LICH 2026", ln=True, align='C')
    pdf.ln(5)

    for role, content in rows:
        label = "KHACH HANG: " if role == "user" else "AI GUIDE: "
        if role == "bot":
            try:
                data = json.loads(content)
                text = data.get("text", "")
                pdf.multi_cell(0, 8, txt=f"{label}\n{text}")
            except:
                pdf.multi_cell(0, 8, txt=f"{label}{content}")
        else:
            pdf.multi_cell(0, 8, txt=f"{label}{content}")
        pdf.ln(4)

    path = f"trip_guide_{sid}.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
