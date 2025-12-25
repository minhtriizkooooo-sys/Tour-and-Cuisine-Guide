import os
import io
import uuid
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS

# Import ReportLab để xử lý PDF chuyên nghiệp
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT

app = Flask(__name__)
CORS(app)

# --- CẤU HÌNH ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_KEY")
DB_PATH = "chat_history.db"
HOTLINE = "+84-908-08-3566"
BUILDER_NAME = "Vietnam Travel AI – Lại Nguyễn Minh Trí"

# --- DATABASE LOGIC ---
def db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                session_id TEXT, 
                role TEXT, 
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# --- PROMPT HỆ THỐNG ---
SYSTEM_PROMPT = """Bạn là chuyên gia du lịch Việt Nam. 
Nhiệm vụ: Trả lời về Lịch sử, Văn hóa, Con người, Ẩm thực, và Gợi ý lịch trình.
Quy tắc:
1. Nếu khách không nêu địa danh cụ thể -> mặc định trả lời về TP. Hồ Chí Minh.
2. Nếu khách nêu địa danh (tỉnh, thành, điểm du lịch) -> Phải trả lời chi tiết điểm đó.
3. Trả lời bằng tiếng Việt, định dạng rõ ràng bằng các icon 📍, 🏛, 👥, 🍜, 🗺.
4. Cuối câu trả lời, hãy đề xuất 3 câu hỏi gợi ý, đặt trong thẻ [SUGGESTIONS] câu 1|câu 2|câu 3 [/SUGGESTIONS]."""

# --- HELPER: SEARCH MEDIA ---
def get_search_media(query):
    # Sử dụng ảnh ngẫu nhiên từ Unsplash theo chủ đề để minh họa
    images = [
        {"url": f"https://source.unsplash.com/800x600/?vietnam,landmark,{query}", "caption": f"Vẻ đẹp {query}"},
        {"url": f"https://source.unsplash.com/800x600/?vietnam,food,{query}", "caption": f"Ẩm thực tại {query}"}
    ]
    videos = [f"https://www.youtube.com/results?search_query=du+lich+{query}"]
    return images, videos

# --- ROUTES ---
@app.route("/")
def index():
    # Tạo mã phiên mới mỗi lần load trang
    sid = str(uuid.uuid4())[:8]
    return render_template("index.html", sid=sid, HOTLINE=HOTLINE, BUILDER=BUILDER_NAME)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    msg = data.get("msg", "")
    sid = data.get("sid", "default")
    
    try:
        # Gọi OpenAI API
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": msg}
                ],
                "temperature": 0.7
            },
            timeout=15
        )
        res = r.json()
        full_reply = res["choices"][0]["message"]["content"]
    except Exception as e:
        full_reply = f"Xin lỗi, tôi gặp chút gián đoạn khi tìm hiểu về {msg}. Nhưng nhìn chung đây là một điểm đến tuyệt vời! [SUGGESTIONS] Chỉ đường đến đây|Thời tiết hiện tại|Món ngon nên thử [/SUGGESTIONS]"

    # Tách văn bản trả lời và phần gợi ý
    reply_text = full_reply.split("[SUGGESTIONS]")[0].strip()
    suggestions = []
    if "[SUGGESTIONS]" in full_reply:
        try:
            s_part = full_reply.split("[SUGGESTIONS]")[1].split("[/SUGGESTIONS]")[0]
            suggestions = [s.strip() for s in s_part.split("|")]
        except:
            suggestions = ["Lịch trình gợi ý", "Giá vé tham khảo", "Đặc sản địa phương"]

    # Lưu vào database
    with db_conn() as conn:
        conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (sid, "user", msg))
        conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (sid, "bot", reply_text))
        conn.commit()

    images, videos = get_search_media(msg)
    return jsonify({
        "reply": reply_text, 
        "suggestions": suggestions, 
        "images": images, 
        "videos": videos
    })

@app.route("/clear-history", methods=["POST"])
def clear_history():
    sid = request.json.get("sid")
    with db_conn() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        conn.commit()
    return jsonify({"status": "deleted"})

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    sid = request.json.get("sid")
    with db_conn() as conn:
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id=? ORDER BY id ASC", (sid,)).fetchall()
    
    buf = io.BytesIO()
    
    # ĐĂNG KÝ FONT TIẾNG VIỆT (Đảm bảo file DejaVuSans.ttf có trong thư mục static)
    font_path = os.path.join("static", "DejaVuSans.ttf")
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        font_main = "DejaVu"
        font_bold = "DejaVu" # Có thể dùng DejaVuSans-Bold.ttf nếu có
    except:
        font_main = "Helvetica"
        font_bold = "Helvetica-Bold"

    # Cấu hình tài liệu PDF
    doc = SimpleDocTemplate(
        buf, 
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    
    styles = getSampleStyleSheet()
    
    # Định dạng style cho Tiếng Việt: Có wordWrap để tự xuống dòng
    style_vn = ParagraphStyle(
        "Vietnamese",
        fontName=font_main,
        fontSize=11,
        leading=16,          # Khoảng cách dòng
        alignment=TA_LEFT,   # Căn lề trái
        wordWrap='CJK',      # Hỗ trợ ngắt dòng tốt cho văn bản dài
    )
    
    style_header = ParagraphStyle(
        "Header",
        parent=styles["Title"],
        fontName=font_main,
        fontSize=18,
        textColor=colors.hexColor("#0f9d58"),
        spaceAfter=20
    )

    story = []
    # Tiêu đề file PDF
    story.append(Paragraph("HÀNH TRÌNH DU LỊCH VIỆT NAM AI", style_header))
    story.append(Paragraph(f"Ngày xuất bản: {datetime.now().strftime('%d/%m/%Y %H:%M')}", style_vn))
    story.append(Spacer(1, 20))

    # Duyệt qua các dòng tin nhắn
    for r in rows:
        is_user = (r["role"] == "user")
        label = "<b>Khách hàng:</b>" if is_user else "<b>Curie AI:</b>"
        bg_color = "#f0f0f0" if not is_user else "#ffffff"
        
        # Thêm nội dung với định dạng xuống dòng tự động
        p = Paragraph(f"{label}<br/>{r['content']}", style_vn)
        story.append(p)
        story.append(Spacer(1, 10)) # Khoảng cách giữa các đoạn chat
    
    # Xây dựng PDF
    doc.build(story)
    buf.seek(0)
    
    return send_file(
        buf, 
        as_attachment=True, 
        download_name=f"HanhTrinh_AI_{sid}.pdf", 
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    # Chạy trên toàn cục để Deploy (Render/Railway/Heroku)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
