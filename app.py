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
import re
import random

app = Flask(__name__)
# Thiết lập Secret Key
app.secret_key = "trip_smart_2026_tri" 
CORS(app)

# --- CẤU HÌNH API KEYS VÀ HỖ TRỢ MULTI-KEY ---
API_KEYS = []
for key, value in os.environ.items():
    # Tìm tất cả các biến chứa API_KEY (GOOGLE_API_KEY, API_KEY_1, v.v.)
    if "API_KEY" in key.upper() and value:
        API_KEYS.extend([k.strip() for k in value.split(',') if k.strip()])

# Lọc các key hợp lệ bắt đầu bằng AIza
API_KEYS = list(set([key for key in API_KEYS if key.startswith('AIza')]))
print(f"[SYSTEM] Đã tìm thấy {len(API_KEYS)} API Keys hợp lệ.")

# Chuyển sang gemini-1.5-flash để có Quota ổn định hơn cho tài khoản Free
model_name = "gemini-1.5-flash" 
DB_PATH = "chat_history.db"

# === SYSTEM INSTRUCTION ===
system_instruction = """
Bạn là AI Hướng dẫn Du lịch Việt Nam chuyên nghiệp (VIET NAM TRAVEL AI GUIDE 2026).
Nhiệm vụ: Cung cấp thông tin du lịch chi tiết, hấp dẫn bằng Tiếng Việt chuẩn.

BẮT BUỘC TRẢ VỀ JSON THUẦN (không có ```json```, không text thừa):
{
  "text": "Nội dung chi tiết Tiếng Việt có dấu, trình bày đẹp bằng Markdown. Phải bao gồm đầy đủ 4 phần chính:\\n1. Lịch sử phát triển và nét đặc trưng địa phương.\\n2. Văn hóa và con người.\\n3. Ẩm thực nổi bật.\\n4. Đề xuất lịch trình cụ thể và gợi ý du lịch.",
  "images": [{"url": "link_ảnh_chất_lượng_cao", "caption": "mô_tả_chính_xác_và_chi_tiết_nội_dung_ảnh"}, ...],
  "youtube_links": ["FULL_URL_youtube_review_thuc_te", ...],
  "suggestions": ["Gợi ý câu hỏi 1", "Gợi ý câu hỏi 2"]
}

YÊU CẦU MEDIA:
1. IMAGES: Sử dụng: https://images.unsplash.com/featured/?{tên_địa_danh_tiếng_anh},vietnam,travel
2. YOUTUBE: Cung cấp link video thực tế từ Khoai Lang Thang, VTV24 hoặc Mùa đi nếm.
"""

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

def get_youtube_id(url):
    if not url: return None
    patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([^&]+)",
        r"(?:https?://)?(?:www\.)?youtu\.be/([^?]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([^?]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1).split('&')[0]
            return video_id
    return None

def get_ai_response(session_id, user_msg):
    if not API_KEYS:
        return {"text": "Lỗi: Không tìm thấy API Key nào trong cấu hình.", "images": [], "youtube_links": []}

    # Lấy lịch sử hội thoại
    history_contents = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 10", (session_id,)).fetchall()
            rows.reverse()
            for r in rows:
                role = "user" if r['role'] == 'user' else "model"
                content_text = r['content']
                if role == "model":
                    try: content_text = json.loads(content_text).get('text', content_text)
                    except: pass
                history_contents.append(types.Content(role=role, parts=[types.Part(text=content_text)]))
    except: pass

    contents = history_contents + [types.Content(role="user", parts=[types.Part(text=user_msg)])]

    # Xáo trộn Key để phân bổ request
    shuffled_keys = API_KEYS.copy()
    random.shuffle(shuffled_keys)

    for key in shuffled_keys:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction, 
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )
            
            if response and response.text:
                ai_data = json.loads(response.text)
                if 'youtube_links' in ai_data:
                    ai_data['youtube_links'] = [l for l in ai_data['youtube_links'] if get_youtube_id(l)]
                return ai_data
                
        except Exception as e:
            error_msg = str(e)
            print(f"[DEBUG] Key lỗi: {key[:10]}... - Lỗi: {error_msg}")
            # Nếu hết hạn mức (429), nhảy sang key tiếp theo
            if "429" in error_msg or "quota" in error_msg.lower():
                continue
            continue

    return {
        "text": "⚠️ Hiện tại tất cả các cổng kết nối AI đều bận hoặc hết hạn mức. Vui lòng thử lại sau ít phút.",
        "images": [],
        "youtube_links": [],
        "suggestions": ["Thử lại sau"]
    }

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
    if not msg: return jsonify({"text": "Vui lòng nhập tin nhắn."})
    
    ai_data = get_ai_response(sid, msg) 
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    for r in rows:
        try: content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
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
        
        font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
        if os.path.exists(font_path):
            pdf.add_font('DejaVu', '', font_path)
            pdf.set_font('DejaVu', '', 11)
        else:
            pdf.set_font('Arial', '', 11)

        for role, content, time_str in rows:
            prefix = "Khách hàng: " if role == "user" else "AI Tư vấn: "
            try:
                data = json.loads(content)
                text = data.get('text', '')
            except: text = content
            # Xóa markdown bold
            text = re.sub(r'(\*\*|__)', '', text)
            pdf.multi_cell(0, 8, txt=f"[{time_str}] {prefix}{text}")
            pdf.ln(2)
        
        return Response(bytes(pdf.output()), mimetype='application/pdf',
                        headers={"Content-Disposition": "attachment;filename=lich-trinh.pdf"})
    except Exception as e:
        return str(e), 500

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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
