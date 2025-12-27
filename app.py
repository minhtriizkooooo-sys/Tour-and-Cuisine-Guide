import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from google import genai
from fpdf import FPDF

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG KEY ----------------
GEMINI_API_KEY = (
    os.environ.get("GEMINI_KEY") or 
    os.environ.get("GEMINI-KEY") or 
    os.environ.get("GEMINI-KEY-1")
)

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Lỗi khởi tạo Gemini: {e}")

DB_PATH = "chat_history.db"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS messages 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)''')
    db.commit()
    db.close()

init_db()

# ---------------- AI LOGIC ----------------
def call_gemini(user_msg):
    if not client: return {"history": "Chưa cấu hình API Key trên Render.", "suggestions": []}
    
    prompt = f"""
    Bạn là chuyên gia du lịch Việt Nam. Hãy trả lời về địa điểm: {user_msg}.
    Yêu cầu trả lời CHÍNH XÁC theo cấu trúc JSON sau:
    {{
      "history": "Lịch sử phát triển và nguồn gốc...",
      "culture": "Nét đặc trưng con người, lễ hội, văn hóa...",
      "cuisine": "Các món ăn đặc sản và địa chỉ ăn ngon...",
      "travel_tips": "Tư vấn thời điểm đi, phương tiện, lưu ý...",
      "image_query": "tên địa danh cụ thể bằng tiếng Anh để tìm ảnh",
      "youtube_keyword": "tên địa danh du lịch để tìm video",
      "suggestions": ["Câu hỏi gợi ý 1", "Câu hỏi gợi ý 2", "Câu hỏi gợi ý 3"]
    }}
    Trả lời bằng tiếng Việt, văn phong lôi cuốn.
    """
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        return {"history": f"Lỗi AI: {str(e)}", "suggestions": ["Thử lại sau"]}

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"error": "No message"})

    ai_data = call_gemini(msg)
    
    db = get_db()
    db.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "user", msg, datetime.now().strftime("%H:%M %d/%m")))
    db.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
               (sid, "bot", json.dumps(ai_data), datetime.now().strftime("%H:%M %d/%m")))
    db.commit()
    
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    db = get_db()
    rows = db.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    history = []
    for r in rows:
        content = r['content']
        if r['role'] == 'bot':
            try: content = json.loads(r['content'])
            except: pass
        history.append({"role": r['role'], "content": content, "time": r['created_at']})
    return jsonify(history)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    db = get_db()
    db.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    db.commit()
    return jsonify({"status": "deleted"})

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    db = get_db()
    rows = db.execute("SELECT role, content FROM messages WHERE session_id = ?", (sid,)).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12) # Lưu ý: Để có Tiếng Việt chuẩn cần file .ttf
    pdf.cell(200, 10, txt="LICH SU CHAT DU LICH", ln=True, align='C')
    
    for row in rows:
        role = "Ban: " if row['role'] == 'user' else "AI: "
        pdf.multi_cell(0, 10, txt=f"{role} {row['content'][:200]}...")
    
    output_path = f"history_{sid}.pdf"
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
