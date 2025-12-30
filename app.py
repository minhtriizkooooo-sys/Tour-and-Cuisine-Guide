# app.py

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
# Nên thay đổi key này khi triển khai
app.secret_key = "trip_smart_2026_tri" 
CORS(app)

# --- CẤU HÌNH API KEYS VÀ HỖ TRỢ MULTI-KEY ---
API_KEYS = []
# Lấy tất cả các khóa từ biến môi trường có chứa "API_KEY"
for key, value in os.environ.items():
    if "API_KEY" in key.upper() and value:
        # Hỗ trợ nhiều khóa cách nhau bằng dấu phẩy
        API_KEYS.extend([k.strip() for k in value.split(',') if k.strip()])
# Loại bỏ trùng lặp và chỉ giữ lại các khóa hợp lệ (bắt đầu bằng 'AIza')
API_KEYS = list(set([key for key in API_KEYS if key.startswith('AIza')]))
print(f"[DEBUG-KEY] Total VALID Keys Found in Environment: {len(API_KEYS)}")

model_name = "gemini-2.5-flash"
DB_PATH = "chat_history.db"

# === SYSTEM INSTRUCTION MẠNH MẼ ===
system_instruction = """
Bạn là AI Hướng dẫn Du lịch Việt Nam chuyên nghiệp (VIET NAM TRAVEL AI GUIDE 2026).
Nhiệm vụ: Cung cấp thông tin du lịch chi tiết, hấp dẫn bằng Tiếng Việt chuẩn về địa điểm người dùng hỏi.

BẮT BUỘT TRẢ VỀ JSON THUẦN (không có ```json```, không text thừa):
{
  "text": "Nội dung chi tiết Tiếng Việt có dấu, trình bày đẹp bằng Markdown. Phải bao gồm đầy đủ 4 phần chính:\\n1. Lịch sử phát triển và nét đặc trưng địa phương.\\n2. Văn hóa và con người.\\n3. Ẩm thực nổi bật.\\n4. Đề xuất lịch trình cụ thể và gợi ý du lịch.",
  "images": [{"url": "link_ảnh", "caption": "mô_tả_ngắn"}, ...],
  "youtube_links": ["https://www.youtube.com/watch?v=ID_11_ký_tự", ...],
  "suggestions": ["Gợi ý câu hỏi 1", "Gợi ý câu hỏi 2"]
}

YÊU CẦU NGHIÊM NGẶT VỀ MEDIA (TUÂN THỦ 100%):
• IMAGES: 
  - CHỈ dùng URL ảnh chất lượng cao, công khai, đang hoạt động từ các nguồn UY TÍN: 
    pexels.com, pixabay.com, unsplash.com
  - Ảnh PHẢI liên quan TRỰC TIẾP và chính xác với địa điểm người dùng hỏi.
  - Caption ngắn gọn, mô tả đúng nội dung ảnh.
  - Tối đa 3 ảnh.
  - Nếu không tìm được ảnh phù hợp tuyệt đối → để mảng rỗng [].

• YOUTUBE_LINKS:
  - CHỈ cung cấp FULL URL hợp lệ (https://www.youtube.com/watch?v=ID_11_ký_tự)
  - Video phải chất lượng cao (HD/4K), liên quan TRỰC TIẾP đến địa điểm (travel vlog, tour thực tế, review mới).
  - Video phải đang công khai và xem được.
  - Tối đa 2 video.
  - Nếu không tìm được video tốt → để mảng rỗng [].

Tuyệt đối không bịa đặt link. Nếu không chắc chắn → để mảng rỗng.
"""
# --- HẾT SYSTEM INSTRUCTION ---

def init_db():
    """Khởi tạo cơ sở dữ liệu SQLite."""
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
    """Trích xuất ID YouTube hợp lệ."""
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
            if len(video_id) == 11:
                 return video_id
    return None

def get_ai_response(session_id, user_msg):
    """Tải lịch sử, gọi API Gemini, và xử lý phản hồi."""
    if not API_KEYS:
        return {"text": "Lỗi cấu hình: Chưa tìm thấy Khóa API Gemini nào.",
                "images": [], "youtube_links": [], "suggestions": []}

    # 1. TẢI LỊCH SỬ HỘI THOẠI TỪ DB
    history_contents = []
    if session_id:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            # Lấy 10 tin nhắn gần nhất (5 lượt chat)
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 10", (session_id,)).fetchall()
            rows.reverse() # Đảo ngược để có thứ tự thời gian
            
            for r in rows:
                role = "user" if r['role'] == 'user' else "model"
                content_text = r['content']
                
                if role == "model":
                    # Nội dung bot được lưu dưới dạng JSON string, chỉ lấy phần 'text' để đưa vào context
                    try:
                        content_json = json.loads(content_text)
                        content_text = content_json.get('text', content_text)
                    except:
                        pass
                
                # SỬA LỖI 1: TẠO PART CHO LỊCH SỬ DỤNG types.Part(text=...)
                history_contents.append(types.Content(role=role, parts=[types.Part(text=content_text)]))

    # 2. XÂY DỰNG CONTENTS CHO API (Lịch sử + Tin nhắn hiện tại)
    # SỬA LỖI 2: TẠO PART CHO TIN NHẮN HIỆN TẠI DỤNG types.Part(text=...)
    contents = history_contents + [types.Content(role="user", parts=[types.Part(text=user_msg)])]

    # 3. QUAY VÒNG KEY VÀ GỌI API
    for i, key in enumerate(API_KEYS):
        try:
            client = genai.Client(api_key=key)
            
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction, # Đặt System Instruction ở đây
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )
            
            print(f"[DEBUG-AI] Raw AI Response (Key {i+1}): {response.text[:200]}...")
            
            # Phản hồi từ AI phải là JSON, tiến hành parse
            ai_data = json.loads(response.text)
            
            # === LỌC NGHIÊM NGẶT MEDIA SAU KHI NHẬN ===
            # Images: chỉ giữ từ nguồn uy tín
            if 'images' in ai_data:
                valid_images = []
                for img in ai_data.get('images', []):
                    url = img.get('url', '')
                    if any(domain in url.lower() for domain in ['pexels.com', 'pixabay.com', 'unsplash.com', 'images.pexels.com', 'cdn.pixabay.com']):
                        valid_images.append(img)
                ai_data['images'] = valid_images[:3]

            # YouTube: chỉ giữ link hợp lệ
            if 'youtube_links' in ai_data:
                valid_links = [link for link in ai_data['youtube_links'] if get_youtube_id(link)]
                ai_data['youtube_links'] = valid_links[:2]
            
            return ai_data
            
        except json.JSONDecodeError as json_err:
            print(f"Lỗi JSON Decode (Key {i+1}): {json_err}. Phản hồi: {response.text[:100]}")
            continue
        except Exception as e:
            print(f"Lỗi API (Key {i+1}): {e}")
            continue

    return {"text": "Tất cả Khóa API đều đã hết hạn mức hoặc lỗi. Vui lòng thử lại sau.",
            "images": [], "youtube_links": [], "suggestions": []}

# === ĐỊNH TUYẾN FLASK ===

@app.route("/")
def index():
    """Trang chủ, thiết lập session_id (cookie)."""
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    # Thêm cookie session_id (HttpOnly để tăng bảo mật)
    resp.set_cookie("session_id", sid, httponly=True) 
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    """Xử lý tin nhắn chat mới."""
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    msg = request.json.get("msg", "").strip()
    if not msg: return jsonify({"text": "Vui lòng nhập tin nhắn."})
    
    ai_data = get_ai_response(sid, msg) 
    
    # Lưu lịch sử vào DB
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    """Lấy lịch sử chat của phiên hiện tại."""
    sid = request.cookies.get("session_id")
    if not sid: return jsonify([])
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    res = []
    for r in rows:
        try:
            # Parse nội dung bot từ JSON để hiển thị
            content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
        except: content = r['content']
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    """Xuất lịch sử chat thành file PDF (Hỗ trợ tiếng Việt nếu có font)."""
    sid = request.cookies.get("session_id")
    if not sid: return "Không có lịch sử", 400
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
            
        pdf = FPDF()
        pdf.add_page()
        
        # Cấu hình font tiếng Việt (Cần đảm bảo file DejaVuSans.ttf nằm trong thư mục static)
        font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
        
        if os.path.exists(font_path):
            pdf.add_font('DejaVu', '', font_path)
            pdf.set_font('DejaVu', '', 14)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 10, txt="LỊCH TRÌNH DU LỊCH SMART TRAVEL 2026", ln=True, align='C')
            pdf.set_font('DejaVu', '', 11)
        else:
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 10, txt="LICH TRINH SMART TRAVEL 2026 (Font Viet Nam khong duoc ho tro)", ln=True, align='C')
            
        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)
        
        for role, content, time_str in rows:
            prefix = "Khách hàng: " if role == "user" else "AI Tư vấn: "
            try:
                # Xử lý nội dung Bot (JSON)
                data = json.loads(content)
                text = data.get('text', '')
                if data.get('images'):
                    for img in data['images']:
                        text += f"\n [Ảnh: {img.get('caption', 'Hình ảnh')} - {img['url']}]"
                if data.get('youtube_links'):
                    for link in data['youtube_links']:
                        text += f"\n [Video YouTube: {link}]"
            except:
                # Xử lý nội dung User (text thuần)
                text = content
            
            # Dọn dẹp Markdown cơ bản cho PDF
            text = re.sub(r'(\*\*|__)', '', text)
            text = re.sub(r'^\* ', '- ', text, flags=re.MULTILINE)
            
            pdf.multi_cell(0, 8, txt=f"[{time_str}] {prefix}{text}")
            pdf.ln(3)
            
        pdf_bytes = bytes(pdf.output())
        
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={"Content-Disposition": "attachment;filename=lich-trinh-2026.pdf"}
        )
    except Exception as e:
        print(f"Lỗi khi xuất PDF: {str(e)}")
        return f"Lỗi khi xuất PDF: {str(e)}", 500

@app.route("/clear_history", methods=["POST"])
def clear_history():
    """Xóa lịch sử chat hiện tại và tạo session_id mới."""
    sid = request.cookies.get("session_id")
    if sid:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
            
    resp = jsonify({"status": "ok"})
    # Đặt cookie mới để bắt đầu phiên mới
    resp.set_cookie("session_id", str(uuid.uuid4()), httponly=True) 
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
