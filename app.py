import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF
from PIL import Image
import requests
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DB_PATH = "chat_history.db"

# SYSTEM PROMPT SIÊU CHẶT CHẼ - BẮT BUỘC ảnh & video THỰC TẾ, CHẤT LƯỢNG CAO
SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch Việt Nam hàng đầu, trả lời cực kỳ chi tiết và hấp dẫn bằng tiếng Việt.

Trả về JSON hợp lệ strictly theo cấu trúc sau:
{
  "text": "# [Tên địa danh]\\n\\n## ⏳ Lịch sử...\\n[chi tiết dài >800 từ]...",
  "images": [
    {"url": "https://direct-link-to-real-high-quality.jpg", "caption": "Mô tả ngắn hấp dẫn"}
  ],
  "youtube_links": ["https://www.youtube.com/watch?v=VIDEO_ID_THỰC_TẾ"],
  "suggestions": ["Gợi ý 1", "Gợi ý 2", ...]
}

YÊU CẦU BẮT BUỘC:
- images: CHỈ dùng link direct (.jpg hoặc .png) từ nguồn UY TÍN, CHẤT LƯỢNG CAO, THỰC TẾ:
  + https://images.unsplash.com/... (Unsplash)
  + https://images.pexels.com/photos/...
  + https://upload.wikimedia.org/wikipedia/commons/...
  Tuyệt đối KHÔNG dùng link random, placeholder, hoặc link có thể die.
  Chọn 5-7 ảnh đẹp nhất, đa dạng góc chụp, liên quan trực tiếp đến địa danh và nội dung.

- youtube_links: CHỈ dùng video YouTube THỰC TẾ, chất lượng cao (1080p+), cập nhật gần đây (2023-2026), nội dung travel vlog/review chân thực về đúng địa danh.
  Ưu tiên video có hình ảnh đẹp, tiếng Việt hoặc tiếng Anh rõ ràng.
  Chọn 4-6 video hay nhất.

- suggestions: 5-7 gợi ý câu hỏi tiếp theo thông minh.

Chỉ trả về JSON thuần, không thêm bất kỳ text nào khác.
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
        ai_data = {"text": f"Lỗi xử lý: {str(e)}", "images": [], "youtube_links": [], "suggestions": []}

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

    # Font tiếng Việt
    font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=14)
    else:
        pdf.set_font("Arial", size=14)

    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 15, "VIETNAM TRAVEL AI GUIDE 2026", ln=True, align='C')
    pdf.set_font("DejaVu", size=12) if os.path.exists(font_path) else pdf.set_font("Arial", size=12)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()

        for r in rows:
            if r['role'] == 'user':
                pdf.set_font("DejaVu", 'B', 12) if os.path.exists(font_path) else pdf.set_font("Arial", 'B', 12)
                pdf.multi_cell(0, 8, f"Bạn: {r['content']}")
                pdf.ln(5)
            else:
                try:
                    data = json.loads(r['content'])
                    text = data.get('text', '')
                    images = data.get('images', [])
                    youtube_links = data.get('youtube_links', [])
                except:
                    text = r['content']
                    images = []
                    youtube_links = []

                if text:
                    pdf.set_font("DejaVu", size=11) if os.path.exists(font_path) else pdf.set_font("Arial", size=11)
                    pdf.multi_cell(0, 7, text)
                    pdf.ln(8)

                # Thêm ảnh vào PDF (nếu có)
                for img in images[:6]:  # Giới hạn 6 ảnh để PDF không quá nặng
                    url = img['url']
                    caption = img.get('caption', 'Hình ảnh du lịch')
                    try:
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            img_data = BytesIO(response.content)
                            img = Image.open(img_data)
                            img_width, img_height = img.size
                            max_width = 180
                            ratio = max_width / img_width
                            new_height = img_height * ratio
                            pdf.image(url, w=max_width, h=new_height)
                            pdf.set_font("DejaVu", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                            pdf.multi_cell(0, 6, caption)
                            pdf.ln(8)
                    except:
                        continue  # Bỏ qua nếu ảnh lỗi

                # Thêm link YouTube
                if youtube_links:
                    pdf.set_font("DejaVu", 'B', 11) if os.path.exists(font_path) else pdf.set_font("Arial", 'B', 11)
                    pdf.cell(0, 8, "Video tham khảo thực tế:", ln=True)
                    pdf.set_font("DejaVu", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                    for link in youtube_links[:6]:
                        pdf.cell(0, 7, link, ln=True, link=link)
                    pdf.ln(10)

    pdf_file = "Lich_Trinh_Du_Lich_Viet_Nam_2026.pdf"
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
