# ==============================
# app.py – CLEAN FINAL VERSION (EXTENDED)
# ==============================

import os
import io
import uuid
import sqlite3
import requests
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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
DB_PATH = os.getenv("SQLITE_PATH", "chat_history.db")

HOTLINE = "+84-908-08-3566"
BUILDER_NAME = "Vietnam Travel AI – Tours, Cuisine & Culture Guide - Lại Nguyễn Minh Trí"
DEFAULT_CITY = "Thành phố Hồ Chí Minh"

# ================= DATABASE =================
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = db()
    cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id TEXT PRIMARY KEY,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        created_at TEXT
    )""")
    c.commit()
    c.close()

init_db()

# ================= SESSION =================
def get_session():
    sid = request.cookies.get("sid")
    if not sid:
        sid = str(uuid.uuid4())
        c = db()
        c.execute(
            "INSERT INTO sessions VALUES (?,?)",
            (sid, datetime.utcnow().isoformat())
        )
        c.commit()
        c.close()
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

def clear_history(sid):
    c = db()
    c.execute("DELETE FROM messages WHERE session_id=?", (sid,))
    c.commit()
    c.close()

# ================= OPENAI =================
SYSTEM_PROMPT = f"""
Bạn là chuyên gia du lịch và văn hóa Việt Nam.

NGUYÊN TẮC BẮT BUỘC:
- Nếu người dùng KHÔNG nói rõ địa điểm → mặc định {DEFAULT_CITY}
- Nếu người dùng CÓ nêu địa điểm → BẮT BUỘC trả lời đúng địa điểm đó
- TUYỆT ĐỐI KHÔNG từ chối trả lời địa điểm cụ thể
- Không trả lời chung chung
- Không xin lỗi vô lý

CHỦ ĐỀ:
- Du lịch
- Văn hóa
- Lịch sử
- Con người địa phương
- Ẩm thực
- Gợi ý tham quan

FORMAT:
📍 Giới thiệu
🏛 Lịch sử – Văn hóa
👥 Con người
🍜 Ẩm thực
🗺 Gợi ý tham quan
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

# ================= CHAT =================
@app.route("/chat", methods=["POST"])
def chat():
    sid = get_session()
    msg = request.json.get("msg", "").strip()
    if not msg:
        return jsonify({"error": "empty"}), 400

    save_msg(sid, "user", msg)
    reply = ask_gpt(history(sid))
    save_msg(sid, "assistant", reply)

    # ---- enrich response (KHÔNG ẢNH HƯỞNG GPT) ----
    place = msg

    response = {
        "reply": reply,

        "images": [
            {
                "url": "https://upload.wikimedia.org/wikipedia/commons/6/6b/Hoan_Kiem_Lake.jpg",
                "caption": f"Hình ảnh tiêu biểu tại {place}"
            }
        ],

        "youtube": [
            {
                "title": f"Khám phá {place}",
                "video_id": "dQw4w9WgXcQ"
            }
        ],

        "suggestions": [
            f"Văn hóa {place}",
            f"Ẩm thực {place}",
            f"Lịch trình du lịch {place}"
        ]
    }

    return jsonify(response)

@app.route("/history")
def api_history():
    sid = get_session()
    return jsonify({"history": history(sid)})

@app.route("/clear-history", methods=["POST"])
def api_clear():
    sid = get_session()
    clear_history(sid)
    return jsonify({"ok": True})

# ================= PDF =================
def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, f"{BUILDER_NAME} | {HOTLINE}")
    canvas.restoreState()

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    sid = get_session()
    logs = history(sid)

    buf = io.BytesIO()
    pdfmetrics.registerFont(
        TTFont("DejaVu", os.path.join(app.static_folder, "DejaVuSans.ttf"))
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "VN",
            fontName="DejaVu",
            fontSize=11,
            leading=16,
            spaceAfter=10
        )
    )

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )

    story = [
        Paragraph("<b>LỊCH SỬ HỘI THOẠI</b>", styles["VN"]),
        Spacer(1, 14),
    ]

    for m in logs:
        role = "👤 Người dùng" if m["role"] == "user" else "🤖 Trợ lý"
        story.append(
            Paragraph(f"<b>{role}</b><br/>{m['content']}", styles["VN"])
        )
        story.append(Spacer(1, 8))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name="lich_su_chat.pdf",
        mimetype="application/pdf"
    )

# ================= HOME =================
@app.route("/")
def index():
    sid = get_session()
    r = make_response(
        render_template("index.html", HOTLINE=HOTLINE, BUILDER=BUILDER_NAME)
    )
    r.set_cookie("sid", sid, httponly=True, samesite="Lax")
    return r

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
