import os
import uuid
import sqlite3
import json
import unicodedata
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
import google.generativeai as genai
from fpdf import FPDF

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG AI ----------------
# Lấy API Key từ Environment Variable trên Render
GEMINI_API_KEY = os.environ.get("GEMINI_KEY")
model = None

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

DB_PATH = "chat_history.db"

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

# ---------------- UTILS ----------------
def remove_accents(input_str):
    """Xóa dấu để PDF không lỗi font trên Linux/Render"""
    if not input_str: return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def call_gemini(user_msg):
    if not model:
        return {"history": "Vui lòng cấu hình GEMINI_KEY trên Render.", "suggestions": []}
    
    # Prompt ép AI trả về JSON chuẩn cho giao diện
    prompt = (
        f"Bạn là chuyên gia du lịch Việt Nam. Hãy kể về {user_msg}. "
        "Trả về JSON thuần (không markdown) gồm: history, culture, cuisine, travel_tips, image_query, youtube_keyword, suggestions (list 3 câu)."
    )
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"AI Error: {e}")
        return {"history": "AI đang bận, thử lại sau nhé!", "suggestions": ["Hỏi địa điểm khác"]}

# ---------------- ROUTES ----------------
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
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                   (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                   (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    
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
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ?", (sid,)).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=10) # Dùng font chuẩn máy tính để không lỗi
    pdf.cell(200, 10, txt="LICH SU DU LICH - SMART TRAVEL AI", ln=True, align='C')
    pdf.ln(5)

    for role, content in rows:
        label = "BAN: " if role == 'user' else "AI: "
        text_body = content
        if role == 'bot':
            try:
                d = json.loads(content)
                text_body = f"Lich su: {d.get('history','')}\nAm thuc: {d.get('cuisine','')}"
            except: pass
        
        # Chuyển văn bản về dạng không dấu cho PDF
        pdf.multi_cell(0, 8, txt=remove_accents(f"{label} {text_body}"))
        pdf.ln(2)
    
    output_path = "/tmp/travel_history.pdf"
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

@app.route("/clear_history", methods=["POST"])
def clear():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "deleted"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
