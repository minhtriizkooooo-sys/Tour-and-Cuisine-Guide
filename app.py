import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF
import requests
from PIL import Image
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DB_PATH = "chat_history.db"

# PROMPT SIÊU CHẶT - BẮT BUỘC DÙNG NGUỒN ỔN ĐỊNH, LIÊN QUAN CHÍNH XÁC
SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch Việt Nam hàng đầu, trả lời bằng tiếng Việt, chi tiết (>1200 từ), hấp dẫn.

Trả về JSON hợp lệ đúng cấu trúc sau:
{
  "text": "# [Tên địa danh chính]\\n\\n[Mô tả mở đầu sống động]\\n[HÌNH 1][HÌNH 2][HÌNH 3][HÌNH 4]\\n\\n## ⏳ Lịch sử hình thành\\n[chi tiết]\\n[HÌNH 5][HÌNH 6]\\n\\n## 🎭 Văn hóa đặc trưng\\n[chi tiết]\\n[HÌNH 7][HÌNH 8]\\n\\n## 🍲 Ẩm thực tiêu biểu\\n[chi tiết]\\n[HÌNH 9][HÌNH 10]\\n\\n## 📅 Lịch trình gợi ý 4-5 ngày\\n[chi tiết lịch trình]\\n[HÌNH 11][HÌNH 12]\\n\\n### 🎥 Video khám phá thực tế hay nhất\\n- https://www.youtube.com/watch?v=...\\n- https://www.youtube.com/watch?v=...\\n\\n### 💡 Gợi ý tiếp theo:\\n- Gợi ý 1\\n- Gợi ý 2...",
  "images": [
    {"url": "https://upload.wikimedia.org/... hoặc https://images.pexels.com/photos/...jpg", "caption": "Mô tả ngắn bằng tiếng Việt"}
  ],
  "youtube_links": ["https://www.youtube.com/watch?v=VIDEO_ID_LIÊN_QUAN_CHÍNH_XÁC"],
  "suggestions": ["Gợi ý câu hỏi tiếp theo"]
}

YÊU CẦU BẮT BUỘC - KHÔNG ĐƯỢC VI PHẠM:
- Luôn chèn đúng 12 placeholder [HÌNH 1] đến [HÌNH 12] vào vị trí hợp lý trong text.
- images: Chính xác 12 ảnh thực tế, chất lượng cao, direct link từ:
  + Wikimedia Commons (ưu tiên hàng đầu): https://upload.wikimedia.org/wikipedia/commons/...
  + Pexels (direct link original): https://images.pexels.com/photos/.../pexels-photo-....jpeg
  + Flickr CC0/Public Domain: https://live.staticflickr.com/...
  TUYỆT ĐỐI KHÔNG dùng Unsplash, không link có ?w= hoặc parameter dễ bị block/die.
- youtube_links: 5-6 video thực tế, chất lượng cao (1080p+), cập nhật 2022-2026, đúng địa danh, từ kênh uy tín (Vietnam Tourism, travel vloggers nổi tiếng).
- suggestions: 6-8 gợi ý thông minh.
Chỉ trả về JSON thuần, không thêm bất kỳ text nào khác!
"""

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

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=365*24*3600)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg:
        return jsonify({"text": "Vui lòng nhập câu hỏi!", "images": [], "youtube_links": [], "suggestions": []})
    if not GROQ_API_KEY:
        return jsonify({"text": "Lỗi: Thiếu GROQ_API_KEY", "images": [], "youtube_links": [], "suggestions": []})

    client = Groq(api_key=GROQ_API_KEY)
    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            temperature=0.7,
            max_tokens=4096,
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        ai_data = {"text": f"Lỗi: {str(e)}", "images": [], "youtube_links": [], "suggestions": []}

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        for r in rows:
            content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
            res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=13)
    else:
        pdf.set_font("Arial", size=13)

    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 15, "VIETNAM TRAVEL AI GUIDE 2026", ln=True, align='C')
    pdf.ln(10)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()

        for r in rows:
            if r['role'] == 'user':
                pdf.set_font("DejaVu", size=12) if os.path.exists(font_path) else pdf.set_font("Arial", size=12)
                pdf.set_text_color(0, 100, 200)
                pdf.multi_cell(0, 8, f"Bạn: {r['content']}")
                pdf.ln(6)
            else:
                try:
                    data = json.loads(r['content'])
                    text = data.get('text', '').strip()
                    images = data.get('images', [])
                    youtube_links = data.get('youtube_links', [])
                except:
                    text = r['content']
                    images = []
                    youtube_links = []

                if text:
                    pdf.set_font("DejaVu", size=11) if os.path.exists(font_path) else pdf.set_font("Arial", size=11)
                    pdf.set_text_color(0, 0, 0)
                    pdf.multi_cell(0, 7, text)
                    pdf.ln(8)

                for img in images[:6]:
                    url = img['url']
                    caption = img.get('caption', 'Hình ảnh du lịch')
                    try:
                        response = requests.get(url, timeout=15)
                        if response.status_code == 200:
                            img_data = BytesIO(response.content)
                            img_pil = Image.open(img_data)
                            w, h = img_pil.size
                            max_w = 170
                            ratio = max_w / w
                            new_h = h * ratio
                            pdf.image(url, w=max_w)
                            pdf.set_font("DejaVu", size=9) if os.path.exists(font_path) else pdf.set_font("Arial", size=9)
                            pdf.multi_cell(0, 5, caption)
                            pdf.ln(8)
                    except:
                        continue

                if youtube_links:
                    pdf.set_font("DejaVu", size=11) if os.path.exists(font_path) else pdf.set_font("Arial", size=11)
                    pdf.set_text_color(200, 0, 0)
                    pdf.cell(0, 8, "Video tham khảo thực tế:", ln=True)
                    pdf.set_font("DejaVu", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                    pdf.set_text_color(0, 0, 180)
                    for link in youtube_links[:6]:
                        pdf.cell(0, 7, link, ln=True, link=link)
                    pdf.ln(10)

    pdf_file = "Lich_Trinh_Du_Lich_2026.pdf"
    pdf.output(pdf_file)
    return send_file(pdf_file, as_attachment=True, download_name="Lich_Trinh_Viet_Nam_2026.pdf")

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
