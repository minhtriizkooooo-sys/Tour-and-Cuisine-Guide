import os, uuid, sqlite3, json, time, random
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, Response
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "trip_smart_2026_tri"
CORS(app)

# Lấy 11 keys từ environment
API_KEYS = [os.environ.get(f"GEMINI-KEY-{i}") for i in range(11) if os.environ.get(f"GEMINI-KEY-{i}")]
clients = [genai.Client(api_key=k) for k in API_KEYS]

DB_PATH = "chat_history.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def call_gemini(user_msg):
    if not clients: return {"text": "Hệ thống chưa có API Key."}
    prompt = (
        f"Bạn là tour guide du lịch Việt Nam. Hãy review: '{user_msg}'. "
        "Yêu cầu trả về JSON chuẩn: {\"text\": \"review chi tiết văn hóa ẩm thực...\", "
        "\"image_url\": \"https://images.unsplash.com/photo-1528127269322-539801943592?q=80&w=1000\", "
        "\"youtube_link\": \"https://www.youtube.com/results?search_query=du+lich+viet+nam\", "
        "\"suggestions\": [\"Ăn gì ở đây?\", \"Chơi gì buổi tối?\"]}"
    )
    try:
        client = random.choice(clients)
        res = client.models.generate_content(model="gemini-1.5-flash", contents=prompt, 
                                            config=types.GenerateContentConfig(response_mime_type="application/json"))
        return json.loads(res.text)
    except: return {"text": "AI đang bảo trì, Trí vui lòng thử lại sau ít phút!"}

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
    data = call_gemini(msg)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)", 
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)", 
                     (sid, "bot", json.dumps(data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    return jsonify(data)

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

@app.route("/clear_history", methods=["POST"])
def clear():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

@app.route("/export_pdf")
def export_pdf():
    # Xuất PDF đơn giản tránh 502
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="LICH TRINH SMART TRAVEL 2026", ln=True, align='C')
    return Response(pdf.output(dest='S'), mimetype='application/pdf')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
