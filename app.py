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
import random # Thêm thư viện random để chọn ngẫu nhiên API key

app = Flask(__name__)
app.secret_key = "trip_smart_2026_tri"
CORS(app)

# --- CẤU HÌNH API KEYS VÀ HỖ TRỢ MULTI-KEY ---
API_KEYS = []
# Duyệt qua tất cả biến môi trường để tìm các key có tên chứa "API_KEY"
for key, value in os.environ.items():
    if "API_KEY" in key.upper() and value:
        # Hỗ trợ dán nhiều key cách nhau bằng dấu phẩy
        API_KEYS.extend([k.strip() for k in value.split(',') if k.strip()])

API_KEYS = list(set([key for key in API_KEYS if key.startswith('AIza')])) # Loại bỏ các key trùng lặp và lọc key hợp lệ
print(f"[DEBUG-KEY] Total VALID Keys Found in Environment: {len(API_KEYS)}")
# --------------------------------------------------------

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

# Hàm trích xuất ID YouTube từ URL (Giữ nguyên)
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
            # Chỉ trả về ID nếu có độ dài 11 ký tự (chuẩn YouTube)
            if len(match.group(1)) == 11:
                 return match.group(1)
    return None

def get_ai_response(user_msg):
    if not API_KEYS:
        return {"text": "Lỗi cấu hình: Chưa tìm thấy Khóa API Gemini nào.", 
                "images": [], "youtube_links": [], "suggestions": []}

    # TĂNG CƯỜNG SYSTEM INSTRUCTION MỚI
    system_instruction = """
    Bạn là AI Hướng dẫn Du lịch Việt Nam (VIET NAM TRAVEL AI GUIDE 2026).
    Nhiệm vụ của bạn là cung cấp thông tin du lịch chi tiết, hấp dẫn, bằng Tiếng Việt chuẩn.
    LUÔN LUÔN trả lời dưới định dạng JSON sau, ngay cả khi không có ảnh hoặc video (chỉ để trống danh sách):
    {
      "text": "Phần nội dung mô tả chi tiết du lịch, dùng markdown (như **đậm**, *nghiêng*, danh sách) để trình bày đẹp và dễ đọc.",
      "images": [
        {"url": "link_anh_chat_luong_cao_lien_quan_1.jpg", "caption": "Chú thích ảnh 1"},
        {"url": "link_anh_chat_luong_cao_lien_quan_2.jpg", "caption": "Chú thích ảnh 2"}
      ],
      "youtube_links": [
        "https://www.youtube.com/watch?v=VIDEO_ID_LIEN_QUAN_1",
        "https://www.youtube.com/watch?v=VIDEO_ID_LIEN_QUAN_2"
      ],
      "suggestions": ["Gợi ý câu hỏi tiếp theo 1", "Gợi ý câu hỏi tiếp theo 2"]
    }
    
    YÊU CẦU ĐẶC BIỆT VỀ MEDIA:
    1. IMAGE URLS: LUÔN SỬ DỤNG các URL ảnh chất lượng cao, dễ truy cập (ví dụ: từ Wikipedia, các trang tin tức du lịch uy tín, hoặc các CDN công cộng), và phải **liên quan trực tiếp** đến nội dung mô tả. KHÔNG sử dụng các link ảnh bị giới hạn truy cập (như Google Drive, private links). Cung cấp tối đa 3 ảnh.
    2. YOUTUBE LINKS: LUÔN CUNG CẤP **LIÊN KẾT ĐẦY ĐỦ** (full URL) của video YouTube LIÊN QUAN TRỰC TIẾP đến địa điểm. Cung cấp tối đa 2 video.

    Nếu bạn không thể tìm thấy ảnh hoặc video phù hợp, chỉ cần để danh sách đó là [] (rỗng).
    """

    for i, key in enumerate(API_KEYS):
        try:
            client = genai.Client(api_key=key)
            
            # Sử dụng hệ thống instruction và prompt đơn giản hơn
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    {"role": "user", "parts": [{"text": system_instruction}]}, # Dùng System Instruction
                    {"role": "user", "parts": [{"text": user_msg}]} # Lời hỏi của user
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.8
                )
            )
            
            # --- DEBUG QUAN TRỌNG MỚI: LOG RAW RESPONSE ---
            # Ghi lại 200 ký tự đầu của JSON để kiểm tra lỗi format
            print(f"[DEBUG-AI] Raw AI Response (Key {i+1}): {response.text[:200]}...")
            
            ai_data = json.loads(response.text)
            
            # Xử lý các link YouTube (Chỉ giữ lại link hợp lệ)
            if 'youtube_links' in ai_data:
                ai_data['youtube_links'] = [link for link in ai_data['youtube_links'] if get_youtube_id(link)]
            
            # Trả về ngay khi thành công
            return ai_data 
            
        except json.JSONDecodeError as json_err:
            # Lỗi nếu AI trả về JSON không hợp lệ
            print(f"Lỗi JSON Decode (Key {i+1}): {json_err}. AI trả về không phải JSON thuần.")
            # Chuyển sang Key tiếp theo
            continue

        except Exception as e:
            # Lỗi API (Key invalid, Quota exceeded, 404 Model Not Found, v.v.)
            print(f"Lỗi API (Key {i+1}): {e}") 
            # Chuyển sang Key tiếp theo
            continue 

    # Nếu tất cả các key đều lỗi
    return {"text": "Tất cả Khóa API đều đã hết hạn mức hoặc không hợp lệ. Vui lòng tạo khóa mới hoặc thử lại sau.", 
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

    ai_data = get_ai_response(msg)

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
            pdf.set_text_color(0, 51, 102)
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
                # Xử lý nội dung AI
                data = json.loads(content)
                text = data.get('text', '')
                
                # Thêm thông tin ảnh/video vào PDF để người dùng dễ tra cứu
                if data.get('images'):
                    for img in data['images']:
                        text += f"\n   [Ảnh: {img.get('caption', 'Hình ảnh')} - {img['url']}]"
                if data.get('youtube_links'):
                    for link in data['youtube_links']:
                        text += f"\n   [Video YouTube: {link}]"
            except: 
                # Nếu là nội dung người dùng hoặc bot trả về JSON lỗi
                text = content
            
            # Xóa các Markdown để fpdf không bị lỗi
            text = re.sub(r'(\*\*|__|#)', '', text) 
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
        # Nếu có lỗi (ví dụ: thiếu font), in ra lỗi
        print(f"Lỗi khi xuất PDF: {str(e)}")
        return f"Lỗi khi xuất PDF: {str(e)}", 500

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
