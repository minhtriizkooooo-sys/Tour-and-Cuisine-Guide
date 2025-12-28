import os, uuid, sqlite3, json, random
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, Response
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "trip_smart_2026_tri"
CORS(app)

API_KEYS = [os.environ.get(f"GEMINI-KEY-{i}") for i in range(11) if os.environ.get(f"GEMINI-KEY-{i}")]
clients = [genai.Client(api_key=k) for k in API_KEYS]
DB_PATH = "chat_history.db"

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
    # Logic gọi Gemini giữ nguyên như cũ của bạn
    # ... (phần call_gemini)
    return jsonify({"text": "AI phản hồi..."}) # Demo, thay bằng kết quả thật

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    res = []
    for r in rows:
        try: content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
        except: content = r['content']
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ?", (sid,)).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    
    # NẠP FONT TIẾNG VIỆT TỪ STATIC
    font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
    if os.path.exists(font_path):
        pdf.add_font('DejaVu', '', font_path, uni=True)
        pdf.set_font('DejaVu', '', 12)
    else:
        pdf.set_font('Arial', '', 12)

    pdf.cell(200, 10, txt="LỊCH TRÌNH DU LỊCH SMART TRAVEL 2026", ln=True, align='C')
    pdf.ln(10)

    for r in rows:
        role = "Khách: " if r[0] == "user" else "AI: "
        try:
            content_data = json.loads(r[1])
            text = content_data.get('text', '')
        except:
            text = r[1]
        
        pdf.multi_cell(0, 8, txt=f"{role}{text}")
        pdf.ln(2)

    # Chuyển output sang bytes để tránh lỗi 502
    return Response(bytes(pdf.output()), mimetype='application/pdf', 
                    headers={"Content-Disposition": "attachment;filename=hanh-trinh-tri.pdf"})

@app.route("/clear_history", methods=["POST"])
def clear():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
