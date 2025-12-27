import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
# Đảm bảo bạn đã set biến môi trường GEMINI_KEY trên Render
GEMINI_API_KEY = os.environ.get("GEMINI_KEY")

client = None
if GEMINI_API_KEY:
    try:
        # Khởi tạo client mới nhất của Google GenAI
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Lỗi khởi tạo AI Client: {e}")

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
    conn.close()

init_db()

def call_gemini(user_msg):
    if not client: 
        return {"history": "Thiếu API Key trên Server", "suggestions": []}
    
    # Prompt ép AI trả về JSON chuẩn để tránh undefined ở giao diện
    prompt = (
        f"Bạn là chuyên gia du lịch Việt Nam. Hãy kể về {user_msg}. "
        "Trả về định dạng JSON thuần túy (không dùng markdown ```json) với các khóa: "
        "history, culture, cuisine, travel_tips, image_query, youtube_keyword, suggestions (list 3 câu)."
    )
    
    try:
        # SỬA LỖI 404: Dùng trực tiếp tên model, config response_mime_type
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"AI Error: {e}")
        return {
            "history": "AI đang bận, bro thử lại nhé!",
            "culture": "N/A", "cuisine": "N/A", "travel_tips": "N/A",
            "image_query": "Vietnam", "youtube_keyword": "Vietnam Travel",
            "suggestions": ["Thử tìm địa điểm khác", "Kiểm tra kết nối"]
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
        # Lưu tin nhắn người dùng
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                   (sid, "user", msg, datetime.now().strftime("%H:%M")))
        # Lưu phản hồi AI (dạng chuỗi JSON)
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                   (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ?", (sid,)).fetchall()
    
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
    # Sử dụng fpdf2 - Thư viện hỗ trợ Unicode tốt hơn
    from fpdf import FPDF
    sid = request.cookies.get("session_id")
    
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ?", (sid,)).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    
    # Giải pháp PDF tiếng Việt: Sử dụng font DejaVuSans (có sẵn trong fpdf2 hoặc cần tải về)
    # Ở đây ta dùng font hệ thống cơ bản, nếu Render không có font VN, 
    # nó sẽ tự fallback hoặc bạn có thể nhúng font .ttf vào thư mục dự án.
    pdf.set_font("Arial", size=12) 
    pdf.cell(200, 10, txt="LICH SU DU LICH VIET NAM", ln=True, align='C')
    pdf.ln(10)

    for row in rows:
        role = "Ban: " if row[0] == 'user' else "AI: "
        # Để tránh lỗi Unicode, ta convert text về dạng an toàn hoặc đảm bảo thư viện hỗ trợ
        text = str(row[1])
        if row[0] == 'bot':
            try:
                data = json.loads(text)
                text = f"Lich su: {data.get('history','')}\nAm thuc: {data.get('cuisine','')}"
            except: pass
        
        # Nếu chưa nhúng font Unicode, dùng hàm encode/decode để tránh sập app
        safe_text = text.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 10, txt=f"{role} {safe_text}")
        pdf.ln(2)
    
    output_path = f"history_{sid}.pdf"
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
