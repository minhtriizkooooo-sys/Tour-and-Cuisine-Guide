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
import re # Import module regex để xử lý link YouTube

app = Flask(__name__)
app.secret_key = "trip_smart_2026_tri"
CORS(app)

# --- CẤU HÌNH API KEYS ---
API_KEYS = [
    os.environ.get("GOOGLE_API_KEY"),
    os.environ.get("GEMINI_API_KEY") 
]
API_KEYS = [k for k in API_KEYS if k]

model_name = "gemini-2.5-flash" # Đảm bảo tên model chính xác

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

# Hàm trích xuất ID YouTube từ URL
def get_youtube_id(url):
    if not url: return None
    patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([^&]+)",
        r"(?:https?://)?(?:www\.)?youtu\.be/([^?]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def call_gemini(user_msg):
    print(f"[DEBUG-KEY] Keys found: {len(API_KEYS)}") 

    if not API_KEYS:
        return {"text": "Lỗi cấu hình: Chưa tìm thấy Khóa API Gemini trong biến môi trường GOOGLE_API_KEY.", 
                "images": [], "youtube_links": [], "suggestions": []}

    # PROMPT ĐÃ ĐƯỢC CẬP NHẬT ĐỂ YÊU CẦU NỘI DUNG PHONG PHÚ HƠN
    # và trả về JSON chuẩn với danh sách ảnh/video/gợi ý
    prompt = (
        f"Bạn là hướng dẫn viên du lịch Việt Nam chuyên nghiệp và rất chi tiết. "
        f"Người dùng hỏi: '{user_msg}'.\n"
        f"Hãy cung cấp thông tin du lịch chi tiết và hấp dẫn về địa danh được hỏi, bao gồm:\n"
        f"1. Lịch sử phát triển và những nét văn hóa đặc trưng.\n"
        f"2. Con người và ẩm thực địa phương (đặc sản, món ăn nổi tiếng).\n"
        f"3. Gợi ý cụ thể, chi tiết về lịch trình, địa điểm tham quan, trải nghiệm nên thử.\n"
        f"4. Kèm theo 3-5 hình ảnh thực tế (có link url và chú thích tiếng Việt) và 2-3 link video YouTube có thể xem được về địa điểm đó.\n"
        f"5. Đưa ra 3 câu hỏi gợi ý liên quan đến câu trả lời và chủ đề đang nói chuyện.\n"
        f"Trả về JSON thuần (đảm bảo cú pháp JSON hợp lệ): \n"
        "{ \n"
        "  \"text\": \"nội dung trả lời chi tiết tiếng Việt có dấu\", \n"
        "  \"images\": [ \n"
        "    {\"url\": \"link_anh_1.jpg\", \"caption\": \"Chú thích ảnh 1\"}, \n"
        "    {\"url\": \"link_anh_2.jpg\", \"caption\": \"Chú thích ảnh 2\"} \n"
        "  ], \n"
        "  \"youtube_links\": [\"link_video_1\", \"link_video_2\"], \n"
        "  \"suggestions\": [\"Gợi ý câu hỏi 1\", \"Gợi ý câu hỏi 2\", \"Gợi ý câu hỏi 3\"] \n"
        "}"
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
            # Đảm bảo response.text là JSON hợp lệ
            ai_data = json.loads(response.text)
            
            # Xử lý các link YouTube để chỉ lấy ID, nếu cần nhúng iframe
            if 'youtube_links' in ai_data:
                ai_data['youtube_links'] = [link for link in ai_data['youtube_links'] if get_youtube_id(link)]
            
            return ai_data
        except Exception as e:
            print(f"Lỗi khi gọi Gemini API: {e}") 
            continue 

    return {"text": "Hết lượt dùng hôm nay hoặc Khóa API của bạn không hợp lệ.", 
            "images": [], "youtube_links": [], "suggestions": []}

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
        # Lưu toàn bộ JSON response vào DB để khi hiển thị lịch sử không bị mất thông tin ảnh/video
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
            # Khi tải lịch sử, phải parse lại JSON để lấy đủ thông tin
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
                # Thêm thông tin ảnh/video vào PDF nếu có
                if data.get('images'):
                    for img in data['images']:
                        text += f"\n   [Ảnh: {img.get('caption', 'Hình ảnh')} - {img['url']}]"
                if data.get('youtube_links'):
                    for link in data['youtube_links']:
                        text += f"\n   [Video YouTube: {link}]"
            except: 
                text = content
            
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
