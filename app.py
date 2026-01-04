import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026")
CORS(app)

# Lấy API Key từ Environment (Render, Railway, etc.)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DB_PATH = "chat_history.db"

# SYSTEM PROMPT MỚI - Đảm bảo hình ảnh & video THỰC TẾ, chất lượng cao
SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch Việt Nam giàu kinh nghiệm, nhiệt huyết và am hiểu sâu sắc. 
Trả về JSON hợp lệ với nội dung cực kỳ chi tiết, hấp dẫn (text > 800 từ), hoàn toàn bằng tiếng Việt.

Cấu trúc JSON bắt buộc:
{
  "text": "# [Tên địa danh chính]\\n\\n## ⏳ Lịch sử hình thành\\n[chi tiết]\\n\\n## 🎭 Văn hóa đặc trưng\\n[chi tiết]\\n\\n## 🍲 Ẩm thực tiêu biểu\\n[chi tiết]\\n\\n## 📅 Lịch trình gợi ý 3-5 ngày\\n[chi tiết]\\n\\n## 🗺️ Địa điểm nổi bật\\n[chi tiết]\\n...",
  "images": [
    {"url": "URL_DIRECT_ẢNH_THỰC_TẾ.jpg", "caption": "Mô tả ngắn gọn, hấp dẫn bằng tiếng Việt"}
  ],
  "youtube_links": ["https://www.youtube.com/watch?v=VIDEO_ID_THỰC"],
  "suggestions": ["Gợi ý câu hỏi tiếp theo 1", "Gợi ý 2", "Gợi ý 3", ...]
}

YÊU CẦU BẮT BUỘC:
- text: Nội dung phong phú, sống động như hướng dẫn viên thực thụ, sử dụng markdown nhẹ (##, \\n\\n cho đoạn mới).
- images: Chỉ dùng link direct (.jpg hoặc .png) từ nguồn UY TÍN và THỰC TẾ như:
  + Unsplash: https://images.unsplash.com/...
  + Pexels: https://images.pexels.com/photos/...
  + Wikimedia Commons: https://upload.wikimedia.org/...
  Chọn 4-6 ảnh đẹp nhất, chất lượng cao, liên quan trực tiếp đến địa danh và các phần nội dung.
  KHÔNG dùng link random hoặc placeholder.

- youtube_links: Chỉ dùng link YouTube THỰC TẾ, chất lượng cao (1080p+), gần đây (2023-2026 nếu có), nội dung travel vlog/review chân thực.
  Ưu tiên video có phụ đề hoặc tiếng Việt/Anh rõ ràng. Chọn 3-5 video hay nhất.

- suggestions: 4-6 gợi ý câu hỏi tiếp theo thông minh, khuyến khích người dùng khám phá sâu hơn.

Luôn trả về JSON hợp lệ, không thêm bất kỳ text nào ngoài JSON.
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
        return jsonify({"text": "Lỗi hệ thống: Thiếu GROQ_API_KEY", "images": [], "youtube_links": [], "suggestions": []})

    client = Groq(api_key=GROQ_API_KEY)

    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": msg}
            ],
            temperature=0.7,
            max_tokens=4096,
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        ai_data = {
            "text": f"Xin lỗi, có lỗi xảy ra khi xử lý: {str(e)}",
            "images": [],
            "youtube_links": [],
            "suggestions": []
        }

    # Lưu lịch sử chat
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (sid, "user", msg, datetime.now().strftime("%H:%M"))
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M"))
        )

    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)
        ).fetchall()
        for r in rows:
            content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
            res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Thêm font hỗ trợ tiếng Việt (DejaVuSans.ttf phải nằm trong /static)
    font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=12)
    else:
        # Fallback nếu không tìm thấy font (dùng Arial nhưng có thể mất dấu)
        pdf.set_font("Arial", size=12)

    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, "LỊCH TRÌNH DU LỊCH VIỆT NAM - AI GUIDE 2026", ln=True, align='C')
    pdf.ln(10)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)
        ).fetchall()
        
        for r in rows:
            if r['role'] == 'bot':
                try:
                    data = json.loads(r['content'])
                    text = data.get('text', '').strip()
                except:
                    text = r['content']
            else:
                text = f"Bạn: {r['content']}"
            
            if text:
                # Xử lý text để in được nhiều dòng
                pdf.multi_cell(0, 8, txt=text)
                pdf.ln(5)

    pdf_file = "Lich_Trinh_Du_Lich_Viet_Nam.pdf"
    pdf.output(pdf_file)

    return send_file(pdf_file, as_attachment=True, download_name="Lich_Trinh_Du_Lich_Viet_Nam_2026.pdf")

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
