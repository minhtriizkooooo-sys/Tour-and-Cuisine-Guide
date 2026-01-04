import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
import random
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "trip_smart_pro_2026"
CORS(app)

# --- CẤU HÌNH GROQ ---
# Thay key của bạn vào đây hoặc thiết lập trong biến môi trường
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")

DB_PATH = "chat_history.db"

# --- SYSTEM INSTRUCTION ---
system_instruction = """
Bạn là chuyên gia du lịch Việt Nam. Khi người dùng hỏi, trả về JSON với nội dung chi tiết:
1. Lịch sử: Các mốc quan trọng.
2. Văn hóa: Lễ hội, đặc sản con người.
3. Ẩm thực: Tên món + mô tả.

BẮT BUỘC TRẢ VỀ JSON:
{
  "text": "# [Địa danh]\\n## ⏳ Lịch sử\\n...\\n## 🎭 Văn hóa\\n...\\n## 🍲 Ẩm thực\\n...",
  "images": [
    {"url": "https://images.unsplash.com/photo-1528127269322-539801943592?q=80&w=800", "caption": "Cảnh đẹp Việt Nam"},
    {"url": "https://images.unsplash.com/photo-1555949258-eb67b1ef0ceb?q=80&w=800", "caption": "Ẩm thực địa phương"}
  ],
  "youtube_links": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
  "suggestions": ["Món ăn nào nổi tiếng nhất?", "Thời điểm nào đi du lịch tốt nhất?"]
}
Lưu ý: Luôn dùng 'source.unsplash.com' hoặc link ảnh thực tế. Nếu không có ảnh cụ thể, dùng chủ đề chung về du lịch VN.
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def get_ai_response(user_msg):
    client = Groq(api_key=GROQ_API_KEY)
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return ONLY a valid JSON object. " + system_instruction},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        return {"text": f"Lỗi: {str(e)}", "images": [], "suggestions": []}

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=3600*24*7)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    ai_data = get_ai_response(msg)
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
            if r['role'] == 'bot':
                try: res.append({"role": "bot", "content": json.loads(r['content'])})
                except: res.append({"role": "bot", "content": {"text": r['content']}})
            else: res.append({"role": "user", "content": r['content']})
    return jsonify(res)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "LICH TRINH DU LICH VIET NAM", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        for r in rows:
            role = "Ban: " if r['role'] == 'user' else "AI: "
            text = r['content']
            if r['role'] == 'bot':
                try: text = json.loads(text)['text'].replace('#', '').replace('*', '')
                except: pass
            pdf.multi_cell(0, 10, f"{role}{text.encode('latin-1', 'ignore').decode('latin-1')}")
            pdf.ln(5)
            
    pdf_file = "tour_guide.pdf"
    pdf.output(pdf_file)
    return send_file(pdf_file, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
