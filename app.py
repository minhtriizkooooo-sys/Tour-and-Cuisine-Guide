import os
import uuid
import sqlite3
import json
import unicodedata
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_KEY")
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
    model_name = "gemini-2.5-flash"
else:
    client = None

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
    if not client:
        return {"history": "Thiếu API Key!"}
    
    prompt = (
        f"Bạn là hướng dẫn viên du lịch chuyên nghiệp. Hãy kể về {user_msg}. "
        "Trả về JSON thuần: {\"history\": \"...\", \"culture\": \"...\", \"cuisine\": \"...\", "
        "\"travel_tips\": \"...\", \"image_query\": \"...\", \"youtube_keyword\": \"...\", "
        "\"suggestions\": [\"câu 1\", \"câu 2\", \"câu 3\"]}"
    )
    
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            return {
                "history": "Xin lỗi bạn, hôm nay mình đã hết lượt trả lời miễn phí từ Google Gemini (chỉ 20 lượt/ngày). "
                           "Bạn vui lòng thử lại vào ngày mai nhé! 🌅",
                "culture": "", "cuisine": "", "travel_tips": "", "youtube_keyword": "", 
                "suggestions": ["Thử lại ngày mai", "Hỏi về Đà Lạt", "Hỏi về Hạ Long"]
            }
        else:
            return {
                "history": "Xin lỗi, hiện tại mình chưa có thông tin chi tiết về địa điểm này. "
                           "Bạn thử hỏi các địa danh nổi tiếng như Đà Lạt, Hạ Long, Sapa, Phú Quốc nhé! 😊",
                "culture": "", "cuisine": "", "travel_tips": "", "youtube_keyword": "", 
                "suggestions": ["Đà Lạt", "Hạ Long", "Sapa", "Phú Quốc"]
            }

@app.route("/")
def index():
    sid = str(uuid.uuid4())  # Session mới mỗi lần load
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
    if not sid:
        return jsonify([])
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    
    res = []
    for r in rows:
        content = r['content']
        if r['role'] == 'bot':
            try:
                content = json.loads(content)
            except:
                pass
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    if not sid:
        return "Không có phiên chat", 400
    
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id",
            (sid,)
        ).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    font_dir = app.static_folder
    regular_path = os.path.join(font_dir, "DejaVuSans.ttf")
    bold_path = os.path.join(font_dir, "DejaVuSans-Bold.ttf")
    
    if os.path.exists(regular_path):
        pdf.add_font("DejaVu", "", regular_path, uni=True)
    if os.path.exists(bold_path):
        pdf.add_font("DejaVu", "B", bold_path, uni=True)
    
    pdf.set_font("DejaVu", size=16)
    pdf.cell(0, 15, txt="LỊCH SỬ DU LỊCH - SMART TRAVEL AI", ln=True, align='C')
    pdf.ln(10)
    
    for role, content, created_at in rows:
        label = "BẠN: " if role == "user" else "AI: "
        time_str = created_at
        
        pdf.set_font("DejaVu", "B" if os.path.exists(bold_path) else "", 12)
        pdf.multi_cell(0, 10, f"[{time_str}] {label}")
        pdf.ln(5)
        
        pdf.set_font("DejaVu", size=11)
        
        if role == "bot":
            try:
                data = json.loads(content)
                sections = [
                    f"Lịch sử: {data.get('history', '')}",
                    f"Văn hóa: {data.get('culture', '')}",
                    f"Ẩm thực: {data.get('cuisine', '')}",
                    f"Mẹo du lịch: {data.get('travel_tips', '')}",
                    f"YouTube tìm kiếm: {data.get('youtube_keyword', '')}",
                    "Gợi ý địa điểm tiếp theo:",
                ]
                for section in sections:
                    if ':' in section:
                        value = section.split(':', 1)[1].strip()
                        if value:
                            pdf.multi_cell(0, 9, section)
                            pdf.ln(3)
                
                suggestions = data.get('suggestions', [])
                if suggestions:
                    pdf.multi_cell(0, 9, "- " + "\n- ".join(suggestions))
                    pdf.ln(5)
            except:
                pdf.multi_cell(0, 9, content[:1500])
        else:
            pdf.multi_cell(0, 9, content)
        
        pdf.ln(12)
    
    pdf_path = "/tmp/history.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, as_attachment=True, download_name="lich_su_du_lich.pdf")

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
    app.run(host="0.0.0.0", port=10000)
