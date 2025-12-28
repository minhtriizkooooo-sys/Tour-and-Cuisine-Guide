import os
import uuid
import sqlite3
import json
import time
import random
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, session, Response
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "trip_secret_key_2026"
CORS(app)

# --- CẤU HÌNH API KEYS ---
API_KEYS = [v.strip() for k, v in os.environ.items() if k.startswith("GEMINI-KEY-") and v]
clients = []
for key in API_KEYS:
    try:
        clients.append(genai.Client(api_key=key))
    except Exception as e:
        print(f"Lỗi khởi tạo key: {e}")

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
    if not clients:
        return {"history": "Hệ thống chưa có API Key."}

    prompt = (
        f"Bạn là chuyên gia du lịch Việt Nam. Yêu cầu: '{user_msg}'. "
        "Nếu là địa danh: Review lịch sử và ẩm thực. Nếu là lộ trình: Tư vấn đường đi. "
        "Trả về JSON: {\"history\": \"...\", \"cuisine\": \"...\", \"travel_tips\": \"...\", \"suggestions\": [\"...\", \"...\"]}"
    )

    pool = list(clients)
    random.shuffle(pool)

    for client in pool:
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7)
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Lỗi: {e}")
            continue 

    return {"history": "AI đang bận, vui lòng thử lại!"}

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
    result = []
    for r in rows:
        try:
            content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
        except: content = r['content']
        result.append({"role": r['role'], "content": content})
    return jsonify(result)

@app.route("/export_pdf")
def export_pdf():
    try:
        sid = request.cookies.get("session_id")
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
        
        pdf = FPDF()
        pdf.add_page()
        
        font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
        if os.path.exists(font_path):
            pdf.add_font('DejaVu', '', font_path)
            pdf.set_font('DejaVu', '', 11)
        else:
            pdf.set_font("Arial", size=11)

        pdf.cell(0, 10, "SMART TRAVEL AI GUIDE - 2026", ln=True, align='C')
        pdf.ln(5)

        for role, content in rows:
            prefix = "BẠN: " if role == "user" else "AI: "
            text = ""
            if role == "bot":
                try:
                    data = json.loads(content)
                    text = f"{data.get('history','')}\n{data.get('cuisine','')}"
                except: text = str(content)
            else: text = str(content)
            
            pdf.multi_cell(0, 7, txt=f"{prefix} {text}")
            pdf.ln(3)
        
        response = make_response(pdf.output(dest='S'))
        response.headers.set('Content-Disposition', 'attachment', filename='LichTrinh.pdf')
        response.headers.set('Content-Type', 'application/pdf')
        return response
    except Exception as e:
        return f"Lỗi PDF: {str(e)}", 500

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
