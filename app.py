import os
import io
import uuid
import sqlite3
import requests
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from serpapi import GoogleSearch

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT

app = Flask(__name__)
CORS(app)

# CẤU HÌNH BIẾN MÔI TRƯỜNG (Ưu tiên lấy từ Render Settings)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "Dán_Key_Vào_Đây_Nếu_Chạy_Local")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "Dán_Key_Vào_Đây_Nếu_Chạy_Local")
DB_PATH = "chat_history.db"

def db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT)")
        conn.commit()
init_db()

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch Việt Nam. 
Phải trả lời chi tiết về Lịch sử, Văn hóa, Ẩm thực và Lịch trình. 
Định dạng bằng icon 📍, 🏛, 👥, 🍜. Không bao giờ từ chối trả lời địa danh cụ thể.
Cuối bài hãy gợi ý 3 câu hỏi trong thẻ [SUGGESTIONS] câu 1|câu 2|câu 3 [/SUGGESTIONS]."""

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        msg = data.get("msg", "")
        sid = data.get("sid", "default")

        # 1. Gọi SerpApi lấy thông tin thực tế (Tránh trả lời sai lệch)
        images = []
        try:
            search = GoogleSearch({"q": msg, "api_key": SERPAPI_KEY, "hl": "vi", "gl": "vn"})
            res = search.get_dict()
            if "inline_images" in res:
                images = [{"url": img.get("thumbnail"), "caption": img.get("title")} for img in res["inline_images"][:4]]
        except: pass

        # 2. Gọi OpenAI trả lời chi tiết
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
                "temperature": 0.7
            },
            timeout=25
        )
        r.raise_for_status()
        full_reply = r.json()["choices"][0]["message"]["content"]

        reply_text = full_reply.split("[SUGGESTIONS]")[0].strip()
        suggestions = []
        if "[SUGGESTIONS]" in full_reply:
            s_part = full_reply.split("[SUGGESTIONS]")[1].split("[/SUGGESTIONS]")[0]
            suggestions = [s.strip() for s in s_part.split("|")]

        # 3. Lưu lịch sử vào Database
        with db_conn() as conn:
            conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (sid, "user", msg))
            conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (sid, "bot", reply_text))
            conn.commit()

        return jsonify({"reply": reply_text, "suggestions": suggestions, "images": images})
    except Exception as e:
        print(f"Lỗi Server: {e}")
        return jsonify({"reply": f"⚠️ Lỗi hệ thống: {str(e)}"}), 500

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    try:
        sid = request.json.get("sid")
        with db_conn() as conn:
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id=?", (sid,)).fetchall()
        
        buf = io.BytesIO()
        font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", font_path))
            font_name = "DejaVu"
        except: font_name = "Helvetica"

        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        # WordWrap chuẩn tiếng Việt
        style_vn = ParagraphStyle("VN", fontName=font_name, fontSize=11, leading=16, alignment=TA_LEFT)
        
        story = [Paragraph("BÁO CÁO LỊCH TRÌNH DU LỊCH", styles["Title"]), Spacer(1, 20)]
        for r in rows:
            label = "<b>KHÁCH:</b>" if r["role"] == "user" else "<b>CURIE AI:</b>"
            story.append(Paragraph(f"{label}<br/>{r['content']}", style_vn))
            story.append(Spacer(1, 15))
        
        doc.build(story)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name="Tour_Da_Lat.pdf", mimetype="application/pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear", methods=["POST"])
def clear():
    sid = request.json.get("sid")
    with db_conn() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        conn.commit()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
