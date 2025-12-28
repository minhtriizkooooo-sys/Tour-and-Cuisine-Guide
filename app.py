import os, uuid, sqlite3, json, time, random
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
CORS(app)

# --- CẤU HÌNH API KEYS ---
API_KEYS = []
for key_name, value in os.environ.items():
    if key_name.startswith("GEMINI-KEY-") and value:
        API_KEYS.append(value.strip())

clients = []
for key in API_KEYS:
    try:
        clients.append(genai.Client(api_key=key))
    except Exception as e:
        print(f"Bỏ qua key lỗi: {e}")

DB_PATH = "chat_history.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def call_gemini(user_msg):
    if not clients:
        return {"history": "Hệ thống chưa có API Key."}

    prompt = (
        f"Bạn là hướng dẫn viên du lịch VN. Review địa danh hoặc lộ trình: {user_msg}. "
        "Trả về JSON: {\"history\": \"...\", \"culture\": \"...\", \"cuisine\": \"...\", "
        "\"travel_tips\": \"...\", \"youtube_keyword\": \"...\", \"suggestions\": [\"...\", \"...\"]}"
    )

    # Trộn ngẫu nhiên Key để tránh tập trung vào 1 Key gây lỗi 429 nhanh
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
            if "429" in str(e):
                time.sleep(1) # Nghỉ 1s rồi thử key tiếp theo
                continue
            return {"history": f"Lỗi: {str(e)}"}

    return {"history": "Các API Key hiện đang bận (Quota). Trí hãy thử lại sau vài phút nhé!"}

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
    return jsonify([{"role": r['role'], "content": json.loads(r['content']) if r['role']=='bot' else r['content']} for r in rows])

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "LICH SU DU LICH - SMART TRAVEL AI", ln=True, align='C')
    
    for role, content, time in rows:
        if role == "bot":
            try:
                d = json.loads(content)
                text = f"[{time}] AI: {d.get('history')[:100]}..."
            except: text = f"[{time}] AI: {content[:100]}"
        else:
            text = f"[{time}] BAN: {content}"
        pdf.multi_cell(0, 10, text.encode('latin-1', 'ignore').decode('latin-1'))
    
    path = "/tmp/history.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

@app.route("/clear_history", methods=["POST"])
def clear():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
