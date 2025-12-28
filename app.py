import os, uuid, sqlite3, json, time, random
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, Response
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "trip_secret_key_2026"
CORS(app)

# Tự động lấy 11 keys từ GEMINI-KEY-0 đến 10
API_KEYS = [os.environ.get(f"GEMINI-KEY-{i}") for i in range(11) if os.environ.get(f"GEMINI-KEY-{i}")]
clients = [genai.Client(api_key=k) for k in API_KEYS]

DB_PATH = "chat_history.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def call_gemini(user_msg):
    if not clients: return {"text": "Chưa cấu hình API Key."}
    # Prompt yêu cầu trả về cả link ảnh và video thật dựa trên từ khóa
    prompt = (
        f"Bạn là hướng dẫn viên du lịch. Trả lời yêu cầu: '{user_msg}'. "
        "Yêu cầu trả về định dạng JSON: {\"text\": \"nội dung review...\", "
        "\"image_url\": \"https://source.unsplash.com/1600x900/?vị_trí_địa_danh\", "
        "\"youtube_link\": \"https://www.youtube.com/results?search_query=du+lich+địa_danh\", "
        "\"suggestions\": [\"Câu hỏi gợi ý 1\", \"Câu hỏi gợi ý 2\"]}"
    )
    client = random.choice(clients)
    try:
        res = client.models.generate_content(model="gemini-1.5-flash", contents=prompt, 
                                            config=types.GenerateContentConfig(response_mime_type="application/json"))
        return json.loads(res.text)
    except: return {"text": "Hệ thống AI đang bận, Trí vui lòng thử lại sau."}

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
    # Logic xuất PDF đơn giản hóa để tránh lỗi 502
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="LICH TRINH DU LICH", ln=True, align='C')
    return Response(pdf.output(dest='S'), mimetype='application/pdf')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
