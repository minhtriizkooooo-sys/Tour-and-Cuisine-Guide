import os
import uuid
import sqlite3
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
import random
from fpdf import FPDF # Thêm thư viện này

app = Flask(__name__)
app.secret_key = "trip_smart_pro_2026"
CORS(app)

# --- CẤU HÌNH GROQ ---
GROQ_KEYS = []
raw_keys = os.environ.get("GROQ_API_KEY", "")
if raw_keys:
    GROQ_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

DB_PATH = "chat_history.db"

# --- SYSTEM INSTRUCTION NÂNG CẤP (Sửa lỗi ảnh và tăng chiều sâu) ---
system_instruction = """
Bạn là chuyên gia du lịch Việt Nam. Khi người dùng hỏi, trả về JSON với nội dung cực kỳ chi tiết:
1. Lịch sử: Chi tiết mốc thời gian, ý nghĩa lịch sử.
2. Văn hóa: Phong tục, tính cách địa phương, lễ hội đặc sắc.
3. Ẩm thực: Tên món ăn + nguyên liệu + cảm giác khi ăn.

BẮT BUỘC TRẢ VỀ JSON:
{
  "text": "# [Tên địa phương]\\n## ⏳ Lịch sử\\n...\\n## 🎭 Văn hóa\\n...\\n## 🍲 Ẩm thực\\n...",
  "images": [
    {"url": "https://source.unsplash.com/800x600/?vietnam,{tên_địa_danh}", "caption": "Cảnh đẹp thực tế tại địa phương"},
    {"url": "https://source.unsplash.com/800x600/?vietnam,food,{tên_món_ăn}", "caption": "Đặc sản nổi tiếng"}
  ],
  "youtube_links": [
    "https://www.youtube.com/results?search_query=du+lich+{tên_địa_phương}"
  ],
  "suggestions": ["Lịch sử nơi này có gì đặc biệt?", "Món này ăn ở đâu ngon nhất?"]
}
Lưu ý: URL ảnh phải dùng 'source.unsplash.com/800x600/?' để đảm bảo hiển thị tốt trên UI.
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def get_ai_response(user_msg):
    if not GROQ_KEYS: return {"text": "Vui lòng cấu hình API Key.", "images": [], "suggestions": []}
    key = random.choice(GROQ_KEYS).strip()
    client = Groq(api_key=key)
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return ONLY a valid JSON. " + system_instruction},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7,
            max_tokens=3000,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")
        return {"text": "AI đang bận, vui lòng thử lại!", "images": [], "suggestions": []}

# --- ROUTES ---
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
    if not msg: return jsonify({"text": "Bạn muốn hỏi về đâu?"})
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

# --- ROUTE XUẤT PDF ---
@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    pdf = FPDF()
    pdf.add_page()
    # Sử dụng font mặc định có sẵn hoặc Arial (Lưu ý: Để hiển thị tiếng Việt hoàn hảo bạn cần file font .ttf, ở đây dùng Arial cơ bản)
    pdf.set_font("Arial", size=12)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        
        pdf.cell(200, 10, txt="LICH TRINH DU LICH VIET NAM 2026", ln=True, align='C')
        pdf.ln(10)
        
        for r in rows:
            role = "Ban: " if r['role'] == 'user' else "AI: "
            content = r['content']
            if r['role'] == 'bot':
                try:
                    data = json.loads(content)
                    content = data.get('text', '').replace('#', '').replace('*', '')
                except: pass
            
            # Làm sạch ký tự lạ để tránh lỗi PDF font
            clean_text = content.encode('latin-1', 'ignore').decode('latin-1')
            pdf.multi_cell(0, 10, txt=role + clean_text)
            pdf.ln(2)

    pdf_path = f"history_{sid[:8]}.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
