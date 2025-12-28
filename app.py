import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
CORS(app)

# --- CẤU HÌNH API KEYS (Hỗ trợ từ GEMINI-KEY-0 đến GEMINI-KEY-10) ---
API_KEYS = []
for key_name, value in os.environ.items():
    if key_name.startswith("GEMINI-KEY-") and value:
        API_KEYS.append(value.strip())

clients = []
model_name = "gemini-1.5-flash"

for key in API_KEYS:
    try:
        clients.append(genai.Client(api_key=key))
    except Exception as e:
        print(f"Bỏ qua key lỗi: {e}")

DB_PATH = "chat_history.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT, role TEXT, content TEXT, created_at TEXT
            )
        """)
init_db()

def call_gemini(user_msg):
    if not clients:
        return {"history": "Hệ thống chưa có API Key khả dụng.", "suggestions": ["Thử lại sau"]}

    prompt = (
        f"Bạn là hướng dẫn viên du lịch chuyên nghiệp Việt Nam. "
        f"Kể chi tiết về: {user_msg}. Trả về JSON thuần (không markdown): "
        "{\"history\": \"...\", \"culture\": \"...\", \"cuisine\": \"...\", "
        "\"travel_tips\": \"...\", \"image_query\": \"...\", \"youtube_keyword\": \"...\", "
        "\"suggestions\": [\"câu 1\", \"câu 2\"]}"
    )

    # Thử lần lượt qua danh sách các key
    for client in clients:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )
            return json.loads(response.text)
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ["quota", "429", "limit", "exhausted"]):
                continue
            continue

    return {
        "history": "Hôm nay các API Key đã hết lượt dùng (Quota). Vui lòng quay lại sau!",
        "culture": "Bạn vẫn có thể dùng bản đồ và chỉ đường bình thường.",
        "suggestions": ["Tìm địa điểm trên bản đồ", "Hỏi về Đà Lạt"]
    }

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
    if not sid: return jsonify([])
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    res = []
    for r in rows:
        content = r['content']
        if r['role'] == 'bot':
            try: content = json.loads(content)
            except: pass
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    if not sid: return "Không có dữ liệu", 400
    
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    
    # Cài đặt font tiếng Việt (Đảm bảo có file trong static)
    font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path)
        pdf.set_font("DejaVu", size=12)
    else:
        pdf.set_font("Arial", size=12)

    pdf.cell(0, 10, "LỊCH SỬ DU LỊCH - SMART TRAVEL AI", ln=True, align='C')
    pdf.ln(5)

    for role, content, time in rows:
        label = "BẠN: " if role == "user" else "AI: "
        pdf.set_font("DejaVu", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
        
        if role == "bot":
            try:
                data = json.loads(content)
                text = f"[{time}] AI:\n- Lịch sử: {data.get('history')}\n- Văn hóa: {data.get('culture')}"
            except: text = f"[{time}] AI: {content}"
        else:
            text = f"[{time}] BẠN: {content}"
            
        pdf.multi_cell(0, 8, text)
        pdf.ln(4)

    pdf_output = "/tmp/history.pdf"
    pdf.output(pdf_output)
    return send_file(pdf_output, as_attachment=True, download_name="lich_su_du_lich.pdf")

@app.route("/clear_history", methods=["POST"])
def clear():
    sid = request.cookies.get("session_id")
    if sid:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    resp = jsonify({"status": "deleted"})
    resp.set_cookie("session_id", str(uuid.uuid4()), httponly=True)
    return resp

if __name__ == "__main__":
    # Render yêu cầu lấy PORT từ biến môi trường
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
