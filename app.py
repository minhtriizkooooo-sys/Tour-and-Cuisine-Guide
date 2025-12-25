import os
import io
import uuid
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)
CORS(app)

# Cấu hình API Keys (Thay bằng key của bạn)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "YOUR_SERPAPI_KEY") 
DB_PATH = "chat_history.db"

HOTLINE = "+84-908-08-3566"
BUILDER_NAME = "Vietnam Travel AI – Lại Nguyễn Minh Trí"

# Database
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = db()
    c.execute("CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)")
    c.commit()
    c.close()

init_db()

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch Việt Nam. 
Nhiệm vụ: Trả lời về Lịch sử, Văn hóa, Con người, Ẩm thực, và Gợi ý lịch trình.
Quy tắc:
1. Nếu khách không nêu địa danh cụ thể -> mặc định trả lời về TP. Hồ Chí Minh.
2. Nếu khách nêu bất kỳ địa danh nào (tỉnh, thành, điểm du lịch) -> Phải trả lời chi tiết điểm đó, không từ chối.
3. Trả lời bằng tiếng Việt, định dạng rõ ràng bằng các icon 📍, 🏛, 👥, 🍜, 🗺.
4. Cuối câu trả lời, hãy đề xuất 3 câu hỏi gợi ý tiếp theo liên quan chặt chẽ đến nội dung vừa nói, đặt trong thẻ [SUGGESTIONS] câu 1|câu 2|câu 3 [/SUGGESTIONS]."""

def get_search_media(query):
    # Mockup dữ liệu hình ảnh/video dựa trên tìm kiếm (Sử dụng API thật nếu có SerpApi)
    # Ở đây tạo giả lập để đảm bảo code chạy luôn
    images = [
        {"url": f"https://source.unsplash.com/1600x900/?vietnam,{query}", "caption": f"Cảnh đẹp tại {query}"},
        {"url": f"https://source.unsplash.com/1600x900/?travel,{query}", "caption": f"Trải nghiệm du lịch {query}"}
    ]
    videos = [f"https://www.youtube.com/results?search_query=du+lich+{query}"]
    return images, videos

@app.route("/")
def index():
    sid = str(uuid.uuid4())
    return render_template("index.html", sid=sid, HOTLINE=HOTLINE, BUILDER=BUILDER_NAME)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    msg = data.get("msg", "")
    sid = data.get("sid", "default")
    
    # Gọi OpenAI
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            "temperature": 0.7
        }
    )
    res = r.json()
    full_reply = res["choices"][0]["message"]["content"]

    # Tách Suggestion
    reply_text = full_reply.split("[SUGGESTIONS]")[0].strip()
    suggestions = []
    if "[SUGGESTIONS]" in full_reply:
        s_part = full_reply.split("[SUGGESTIONS]")[1].split("[/SUGGESTIONS]")[0]
        suggestions = [s.strip() for s in s_part.split("|")]

    # Lưu db
    conn = db()
    conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (sid, "user", msg))
    conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (sid, "bot", reply_text))
    conn.commit()

    images, videos = get_search_media(msg)
    return jsonify({"reply": reply_text, "suggestions": suggestions, "images": images, "videos": videos})

@app.route("/clear", methods=["POST"])
def clear():
    sid = request.json.get("sid")
    conn = db()
    conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
    conn.commit()
    return jsonify({"status": "ok"})

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    sid = request.json.get("sid")
    conn = db()
    rows = conn.execute("SELECT role, content FROM messages WHERE session_id=?", (sid,)).fetchall()
    
    buf = io.BytesIO()
    # Lưu ý: Cần file DejaVuSans.ttf trong static/
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "static/DejaVuSans.ttf"))
        font_name = "DejaVu"
    except:
        font_name = "Helvetica"

    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    style_vn = ParagraphStyle("VN", fontName=font_name, fontSize=10, leading=14)
    
    story = [Paragraph("LỊCH SỬ TRÒ CHUYỆN", styles["Title"]), Spacer(1, 12)]
    for r in rows:
        label = "Người dùng: " if r["role"] == "user" else "AI: "
        story.append(Paragraph(f"<b>{label}</b> {r['content']}", style_vn))
        story.append(Spacer(1, 6))
    
    doc.build(story)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="lich_su_travel_ai.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
