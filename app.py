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
app.secret_key = "vietnam_travel_expert_2026"
CORS(app)

# --- CẤU HÌNH ---
GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE"  # Thay key của bạn vào đây
DB_PATH = "chat_history.db"

# --- SYSTEM PROMPT CỰC MẠNH ---
# Ép AI phải viết dài, chi tiết và cung cấp link thật
SYSTEM_PROMPT = """
Bạn là một hướng dẫn viên du lịch chuyên nghiệp tại Việt Nam. 
Khi người dùng hỏi về một địa danh, bạn PHẢI trả về JSON với nội dung cực kỳ chi tiết bao gồm:
1. text: Ít nhất 500 từ. Chia làm các mục: # Tổng quan, ## ⏳ Lịch sử hình thành, ## 🎭 Văn hóa & Lễ hội, ## 🍲 Ẩm thực phải thử, ## 📅 Gợi ý lịch trình 1 ngày.
2. images: Cung cấp ít nhất 3 ảnh từ Unsplash. Sử dụng cấu hình: https://source.unsplash.com/800x600/?{keyword} (keyword bằng tiếng Anh).
3. youtube_links: Tìm link video thực tế hoặc trả về link tìm kiếm chính xác: https://www.youtube.com/results?search_query=du+lich+{keyword}.
4. suggestions: 3 câu hỏi sâu hơn về địa danh đó.

BẮT BUỘC ĐỊNH DẠNG JSON:
{
  "text": "nội dung dài...",
  "images": [{"url": "...", "caption": "..."}],
  "youtube_links": ["..."],
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
    user_msg = request.json.get("msg", "").strip()
    
    client = Groq(api_key=GROQ_API_KEY)
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        ai_data = json.loads(completion.choices[0].message.content)
    except Exception as e:
        ai_data = {"text": f"Lỗi kết nối AI: {str(e)}", "images": [], "youtube_links": [], "suggestions": []}

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", user_msg, datetime.now().strftime("%H:%M")))
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

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    pdf = FPDF()
    pdf.add_page()
    # Lưu ý: Font Arial mặc định không có tiếng Việt. Bạn nên dùng font DejaVuSans.ttf nếu có.
    pdf.set_font("Arial", size=12)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        for r in rows:
            text = r['content']
            if r['role'] == 'bot':
                try: text = json.loads(text)['text']
                except: pass
            # Loại bỏ ký tự Unicode lỗi nếu dùng font Arial
            clean_text = text.encode('latin-1', 'ignore').decode('latin-1')
            pdf.multi_cell(0, 10, txt=f"{r['role'].upper()}: {clean_text}")
            pdf.ln(5)

    path = "lich_trinh_du_lich.pdf"
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
