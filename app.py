import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, Response
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "trip_smart_2026_tri"
CORS(app)

# --- CẤU HÌNH API KEYS ---
API_KEYS = [os.environ.get(f"GEMINI-KEY-{i}") for i in range(11)]
API_KEYS = [k for k in API_KEYS if k]  

model_name = "gemini-1.5-flash"
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

def call_gemini(user_msg):
    if not API_KEYS:
        return {"text": "Chưa có API Key!", "image_url": "", "youtube_link": "", "suggestions": []}

    prompt = (
        f"Bạn là hướng dẫn viên du lịch Việt Nam. Người dùng hỏi: {user_msg}\n"
        "Trả về JSON: {\"text\": \"...\", \"image_url\": \"...\", \"youtube_link\": \"...\", \"suggestions\": []}"
    )

    for key in API_KEYS:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.8
                )
            )
            return json.loads(response.text)
        except:
            continue 

    return {"text": "Hết lượt dùng (Quota). Thử lại sau nhé!", "image_url": "", "youtube_link": "", "suggestions": []}

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
    if not msg: return jsonify({"text": "Rỗng!"})

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
    if not sid: return jsonify([])
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    res = []
    for r in rows:
        try:
            content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
        except: content = r['content']
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    if not sid: return "Không có lịch sử", 400

    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()

        pdf = FPDF()
        pdf.add_page()
        
        # Nhúng Font Unicode từ /static
        font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
        if os.path.exists(font_path):
            pdf.add_font('DejaVu', '', font_path)
            pdf.set_font('DejaVu', '', 12)
        else:
            pdf.set_font('Arial', '', 12)

        pdf.cell(0, 10, txt="LICH TRINH SMART TRAVEL 2026", ln=True, align='C')
        pdf.ln(10)

        for role, content, time_str in rows:
            prefix = "Khách hàng: " if role == "user" else "AI: "
            try:
                data = json.loads(content)
                text = data.get('text', '')
            except: text = content
            
            pdf.multi_cell(0, 8, txt=f"[{time_str}] {prefix}{text}")
            pdf.ln(3)

        # FIX LỖI 502: Chuyển bytearray thành bytes
        pdf_bytes = bytes(pdf.output())

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={"Content-Disposition": "attachment;filename=lich-trinh.pdf"}
        )
    except Exception as e:
        return f"Lỗi: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
