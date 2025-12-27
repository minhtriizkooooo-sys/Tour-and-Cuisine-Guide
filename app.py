import os
import uuid
import sqlite3
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
GEMINI_API_KEY = os.environ.get("GEMINI_KEY") or os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")

client = None
if GEMINI_API_KEY:
    try:
        # Cấu hình Client với model chuẩn xác
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Lỗi khởi tạo: {e}")

DB_PATH = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
    conn.commit()
    conn.close()

init_db()

# Hàm loại bỏ dấu tiếng Việt để PDF không bị lỗi (Vì Render không có font VN sẵn)
def no_accent_vietnamese(s):
    s = re.sub(r'[àáạảãâầấậẩẫăằắặẳẵ]', 'a', s)
    s = re.sub(r'[èéẹẻẽêềếệểễ]', 'e', s)
    s = re.sub(r'[ìíịỉĩ]', 'i', s)
    s = re.sub(r'[òóọỏõôồốộổỗơờớợởỡ]', 'o', s)
    s = re.sub(r'[ùúụủũưừứựửữ]', 'u', s)
    s = re.sub(r'[ỳýỵỷỹ]', 'y', s)
    s = re.sub(r'[đ]', 'd', s)
    return s

def call_gemini(user_msg):
    if not client: return {"history": "Thiếu API Key", "suggestions": []}
    
    prompt = f"Bạn là chuyên gia du lịch. Trả lời về {user_msg} dạng JSON: history, culture, cuisine, travel_tips, image_query, youtube_keyword, suggestions (3 câu)."
    
    try:
        # SỬA LỖI 404: Dùng trực tiếp tên model không có prefix 'models/'
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"AI Error: {e}")
        return {"history": "AI đang bận, bro thử lại nhé!", "suggestions": []}

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    msg = request.json.get("msg", "").strip()
    ai_data = call_gemini(msg)
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "user", msg, datetime.now().strftime("%H:%M")))
    conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "bot", json.dumps(ai_data), datetime.now().strftime("%H:%M")))
    conn.commit()
    conn.close()
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM messages WHERE session_id = ?", (sid,)).fetchall()
    res = []
    for r in rows:
        content = r['content']
        if r['role'] == 'bot':
            try: content = json.loads(r['content'])
            except: pass
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    from fpdf import FPDF
    sid = request.cookies.get("session_id")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ?", (sid,)).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="LICH SU CHAT (KHONG DAU)", ln=True, align='C')
    
    for row in rows:
        # Fix lỗi Unicode bằng cách bỏ dấu trước khi cho vào PDF
        clean_text = no_accent_vietnamese(str(row[1]))
        role = "Ban: " if row[0] == 'user' else "AI: "
        pdf.multi_cell(0, 10, txt=f"{role} {clean_text[:300]}")
    
    path = f"chat_{sid}.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

@app.route("/clear_history", methods=["POST"])
def clear():
    sid = request.cookies.get("session_id")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    conn.commit()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
