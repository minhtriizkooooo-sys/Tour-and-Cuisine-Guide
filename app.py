# ==============================
# app.py – FINAL FIXED VERSION
# ==============================

import os, io, uuid, sqlite3, requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ================= CONFIG =================
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DB_PATH = "chat_history.db"

HOTLINE = "+84-908-08-3566"
BUILDER_NAME = "Vietnam Travel AI – Lại Nguyễn Minh Trí"
DEFAULT_CITY = "Thành phố Hồ Chí Minh"

# ================= DATABASE =================
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = db()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)
    c.commit()
    c.close()

init_db()

# ================= SESSION =================
def get_session():
    sid = request.cookies.get("sid")
    if not sid:
        sid = str(uuid.uuid4())
    return sid

def save_msg(sid, role, content):
    c = db()
    c.execute(
        "INSERT INTO messages(session_id, role, content, created_at) VALUES (?,?,?,?)",
        (sid, role, content, datetime.utcnow().isoformat())
    )
    c.commit()
    c.close()

def history(sid):
    c = db()
    rows = c.execute(
        "SELECT role, content FROM messages WHERE session_id=? ORDER BY id",
        (sid,)
    ).fetchall()
    c.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]

def clear_history_db(sid):
    c = db()
    c.execute("DELETE FROM messages WHERE session_id=?", (sid,))
    c.commit()
    c.close()

# ================= OPENAI =================
SYSTEM_PROMPT = f"""
Bạn là trợ lý du lịch và văn hóa Việt Nam.

BẮT BUỘC:
- Trả lời HOÀN TOÀN bằng tiếng Việt
- Không dùng tiếng Anh, không trộn ngôn ngữ
- Nếu không có địa điểm → mặc định {DEFAULT_CITY}
- Trả lời cụ thể, giàu thông tin

SAU MỖI CÂU TRẢ LỜI:
1. Đề xuất 3 câu hỏi tiếp theo phù hợp ngữ cảnh (kiểu ChatGPT)
2. Gợi ý 3–5 hình ảnh thực tế có chú thích
3. Gợi ý 1–2 video YouTube liên quan

FORMAT TRẢ VỀ (JSON):
- reply: string
- images: [{url, caption}]
- videos: [url]
- suggestions: [string]
"""

def ask_gpt(messages):
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "temperature": 0.4,
            "max_tokens": 900
        },
        timeout=60
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def search_images_videos(query):
    images, videos = [], []
    if not SERPAPI_KEY:
        return images, videos

    params = {
        "engine": "google",
        "q": query,
        "tbm": "isch",
        "api_key": SERPAPI_KEY
    }
    r = requests.get("https://serpapi.com/search", params=params).json()
    for img in r.get("images_results", [])[:5]:
        images.append({
            "url": img.get("original"),
            "caption": img.get("title", "")
        })

    params["tbm"] = "vid"
    r = requests.get("https://serpapi.com/search", params=params).json()
    for v in r.get("video_results", [])[:2]:
        videos.append(v.get("link"))

    return images, videos

# ================= CHAT =================
@app.route("/chat", methods=["POST"])
def chat():
    sid = get_session()
    msg = request.json.get("msg", "").strip()
    if not msg:
        return jsonify({"error": "empty"}), 400

    save_msg(sid, "user", msg)
    reply_text = ask_gpt(history(sid))
    save_msg(sid, "assistant", reply_text)

    images, videos = search_images_videos(msg)

    suggestions = [
        f"Lịch sử và văn hóa liên quan đến {msg}",
        f"Ẩm thực đặc trưng tại {msg}",
        f"Gợi ý lịch trình tham quan {msg}"
    ]

    return jsonify({
        "reply": reply_text,
        "images": images,
        "videos": videos,
        "suggestions": suggestions
    })

@app.route("/clear-history", methods=["POST"])
def clear_history():
    sid = get_session()
    clear_history_db(sid)
    return jsonify({"ok": True})

# ================= PDF =================
@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    sid = get_session()
    logs = history(sid)

    buf = io.BytesIO()
    pdfmetrics.registerFont(
        TTFont("DejaVu", os.path.join(app.static_folder, "DejaVuSans.ttf"))
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("VN", fontName="DejaVu", fontSize=11, leading=15))

    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm)

    story = [Paragraph("<b>LỊCH SỬ CHAT</b>", styles["VN"]), Spacer(1, 12)]

    for m in logs:
        role = "Người dùng" if m["role"] == "user" else "Trợ lý"
        story.append(Paragraph(f"<b>{role}:</b><br/>{m['content']}", styles["VN"]))
        story.append(Spacer(1, 8))

    doc.build(story)
    buf.seek(0)

    return send_file(buf, as_attachment=True,
        download_name="lich_su_chat.pdf", mimetype="application/pdf")

# ================= HOME =================
@app.route("/")
def index():
    sid = get_session()
    r = make_response(render_template("index.html", HOTLINE=HOTLINE, BUILDER=BUILDER_NAME))
    r.set_cookie("sid", sid, httponly=True, samesite="Lax")
    return r

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
