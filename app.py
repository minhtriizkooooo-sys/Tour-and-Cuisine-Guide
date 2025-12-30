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

# --- CẤU HÌNH API KEYS ĐÃ CẬP NHẬT (Fix lỗi xóa Key) ---
# Ưu tiên lấy khóa mặc định mới GOOGLE_API_KEY. Nếu không có, thử GEMINI_API_KEY.
API_KEYS = [
    os.environ.get("GOOGLE_API_KEY"),
    os.environ.get("GEMINI_API_KEY") 
]
# Chỉ giữ lại các khóa không rỗng
API_KEYS = [k for k in API_KEYS if k]
# --------------------------------------------------------

# SỬA LỖI: Thay thế tên mô hình để tránh lỗi 404 NOT_FOUND
model_name = "gemini-2.5-flash" 

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
    # DÒNG DEBUG QUAN TRỌNG: Kiểm tra số lượng key (Chắc chắn sẽ là 1)
    print(f"[DEBUG-KEY] Keys found: {len(API_KEYS)}") 

    if not API_KEYS:
        return {"text": "Lỗi cấu hình: Chưa tìm thấy Khóa API Gemini trong biến môi trường GOOGLE_API_KEY.", "image_url": "", "youtube_link": "", "suggestions": []}

    prompt = (
        f"Bạn là hướng dẫn viên du lịch Việt Nam chuyên nghiệp. Người dùng hỏi: {user_msg}\n"
        "Trả về JSON thuần: {\"text\": \"nội dung trả lời chi tiết tiếng Việt có dấu\", \"image_url\": \"...\", \"youtube_link\": \"...\", \"suggestions\": []}"
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
            # Nếu thành công, trả về kết quả ngay
            return json.loads(response.text)
        except Exception as e:
            # Ghi lại lỗi API chi tiết khi thử key
            print(f"Lỗi khi gọi Gemini API: {e}") 
            continue 

    # Nếu tất cả các key đều lỗi hoặc hết lượt (rất hiếm khi xảy ra nếu key hợp lệ)
    return {"text": "Hết lượt dùng hôm nay hoặc Khóa API của bạn không hợp lệ.", "image_url": "", "youtube_link": "", "suggestions": []}

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
        
        # Nhúng Font Unicode từ /static/DejaVuSans.ttf
        font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
        
        if os.path.exists(font_path):
            pdf.add_font('DejaVu', '', font_path)
            pdf.set_font('DejaVu', '', 14)
            pdf.set_text_color(0, 51, 102) # Xanh đậm chuyên nghiệp
            pdf.cell(0, 10, txt="LỊCH TRÌNH DU LỊCH SMART TRAVEL 2026", ln=True, align='C')
            pdf.set_font('DejaVu', '', 11)
        else:
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 10, txt="LICH TRINH SMART TRAVEL 2026", ln=True, align='C')

        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)

        for role, content, time_str in rows:
            prefix = "Khách hàng: " if role == "user" else "AI Tư vấn: "
            try:
                data = json.loads(content)
                text = data.get('text', '')
            except: text = content
            
            pdf.multi_cell(0, 8, txt=f"[{time_str}] {prefix}{text}")
            pdf.ln(3)

        pdf_bytes = bytes(pdf.output())
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={"Content-Disposition": "attachment;filename=lich-trinh-2026.pdf"}
        )
    except Exception as e:
        return f"Lỗi: {str(e)}", 500

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    if sid:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    resp = jsonify({"status": "ok"})
    resp.set_cookie("session_id", str(uuid.uuid4()), httponly=True)
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
