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

# Lấy Key từ Render Environment
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
DB_PATH = "chat_history.db"

SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch Việt Nam. Trả về JSON với nội dung cực kỳ chi tiết (text trên 500 từ).
Cấu trúc JSON bắt buộc:
{
  "text": "# [Tên địa danh]\\n\\n## ⏳ Lịch sử hình thành\\n...\\n## 🎭 Văn hóa đặc trưng\\n...\\n## 🍲 Ẩm thực tiêu biểu\\n...\\n## 📅 Lịch trình gợi ý\\n...",
  "images": [{"url": "https://source.unsplash.com/800x600/?vietnam,{keyword}", "caption": "..."}],
  "youtube_links": ["https://www.youtube.com/embed/[ID_VIDEO_THẬT_HOẶC_GẦN_ĐÚNG]"],
  "suggestions": ["..."]
}
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not GROQ_API_KEY: return jsonify({"text": "Lỗi: Thiếu GROQ_API_KEY"})

    client = Groq(api_key=GROQ_API_KEY)
    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
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
    pdf.set_font("Arial", size=12) # Lưu ý: Muốn có dấu tiếng Việt cần file .ttf
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        for r in rows:
            text = json.loads(r['content'])['text'] if r['role'] == 'bot' else r['content']
            pdf.multi_cell(0, 10, txt=text.encode('latin-1', 'ignore').decode('latin-1'))
            pdf.ln(5)
    
    pdf.output("lich_trinh.pdf")
    return send_file("lich_trinh.pdf", as_attachment=True)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
