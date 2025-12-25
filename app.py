# =====================================================
# app.py
# Vietnam Travel AI – Map + Chatbot + PDF Export
# =====================================================

import os
import io
import uuid
import sqlite3
import requests

from datetime import datetime
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    make_response,
    send_file
)
from flask_cors import CORS

# ================= PDF IMPORT =================
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# =====================================================
# CONFIG
# =====================================================

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

DB_PATH = os.getenv("SQLITE_PATH", "chat_history.db")

HOTLINE = "+84-908-08-3566"
BUILDER_NAME = "Vietnam Travel AI – Tours, Cuisine & Culture Guide - Lại Nguyễn Minh Trí"
DEFAULT_CITY = "Thành phố Hồ Chí Minh"

# =====================================================
# DATABASE
# =====================================================

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # -------- SESSION TABLE --------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT
        )
    """)

    # -------- MESSAGE TABLE --------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()

# =====================================================
# SESSION HANDLING
# =====================================================

def get_session_id():
    sid = request.cookies.get("sid")

    if not sid:
        sid = str(uuid.uuid4())

        conn = get_db()
        conn.execute(
            "INSERT INTO sessions (id, created_at) VALUES (?, ?)",
            (sid, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

    return sid


def save_message(session_id, role, content):
    conn = get_db()
    conn.execute(
        """
        INSERT INTO messages
        (session_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, role, content, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def load_history(session_id):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT role, content
        FROM messages
        WHERE session_id = ?
        ORDER BY id
        """,
        (session_id,)
    ).fetchall()
    conn.close()

    return [
        {"role": r["role"], "content": r["content"]}
        for r in rows
    ]


def clear_history_db(session_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM messages WHERE session_id = ?",
        (session_id,)
    )
    conn.commit()
    conn.close()

# =====================================================
# OPENAI SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = f"""
Bạn là trợ lý du lịch và văn hóa Việt Nam.

NGUYÊN TẮC BẮT BUỘC:
- Chỉ sử dụng tiếng Việt
- Không trộn tiếng Anh
- Nếu không nêu địa điểm → mặc định {DEFAULT_CITY}
- Nếu đã có địa điểm → bám sát địa điểm đó
- Không trả lời chung chung
- Văn phong rõ ràng, dễ đọc

YÊU CẦU NỘI DUNG:
- Văn hóa
- Lịch sử
- Con người
- Ẩm thực
- Du lịch
- Gợi ý trải nghiệm

SAU MỖI CÂU TRẢ LỜI:
- Gợi ý 3 câu hỏi tiếp theo (đúng ngữ cảnh)
"""

# =====================================================
# OPENAI CALL
# =====================================================

def ask_gpt(messages):
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT}
            ] + messages,
            "temperature": 0.4,
            "max_tokens": 900
        },
        timeout=60
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]

# =====================================================
# IMAGE + VIDEO SEARCH (SERPAPI)
# =====================================================

def search_images_videos(query):
    images = []
    videos = []

    if not SERPAPI_KEY:
        return images, videos

    # ---------- IMAGE SEARCH ----------
    img_params = {
        "engine": "google",
        "q": query,
        "tbm": "isch",
        "api_key": SERPAPI_KEY
    }

    img_res = requests.get(
        "https://serpapi.com/search",
        params=img_params,
        timeout=30
    ).json()

    for img in img_res.get("images_results", [])[:5]:
        images.append({
            "url": img.get("original"),
            "caption": img.get("title", "")
        })

    # ---------- VIDEO SEARCH ----------
    vid_params = {
        "engine": "youtube",
        "search_query": query,
        "api_key": SERPAPI_KEY
    }

    vid_res = requests.get(
        "https://serpapi.com/search",
        params=vid_params,
        timeout=30
    ).json()

    for v in vid_res.get("video_results", [])[:2]:
        videos.append(v.get("link"))

    return images, videos

# =====================================================
# CHAT API
# =====================================================

@app.route("/chat", methods=["POST"])
def chat():
    session_id = get_session_id()

    user_msg = request.json.get("msg", "").strip()
    if not user_msg:
        return jsonify({"error": "empty"}), 400

    # ----- SAVE USER MESSAGE -----
    save_message(session_id, "user", user_msg)

    # ----- LOAD HISTORY -----
    msgs = load_history(session_id)

    # ----- GPT RESPONSE -----
    reply_text = ask_gpt(msgs)

    # ----- SAVE BOT MESSAGE -----
    save_message(session_id, "assistant", reply_text)

    # ----- MEDIA -----
    images, videos = search_images_videos(user_msg)

    suggestions = [
        f"Lịch sử và văn hóa liên quan đến {user_msg}",
        f"Ẩm thực đặc trưng tại {user_msg}",
        f"Lịch trình tham quan {user_msg} trong 1 ngày"
    ]

    return jsonify({
        "reply": reply_text,
        "images": images,
        "videos": videos,
        "suggestions": suggestions
    })

# =====================================================
# HISTORY / CLEAR
# =====================================================

@app.route("/history")
def api_history():
    session_id = get_session_id()
    return jsonify({"history": load_history(session_id)})


@app.route("/clear-history", methods=["POST"])
def api_clear():
    session_id = get_session_id()
    clear_history_db(session_id)
    return jsonify({"ok": True})

# =====================================================
# EXPORT PDF
# =====================================================

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    session_id = get_session_id()
    logs = load_history(session_id)

    buffer = io.BytesIO()

    pdfmetrics.registerFont(
        TTFont(
            "DejaVu",
            os.path.join(app.static_folder, "DejaVuSans.ttf")
        )
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="VN",
            fontName="DejaVu",
            fontSize=11,
            leading=15,
            spaceAfter=8
        )
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm
    )

    story = []
    story.append(Paragraph("<b>LỊCH SỬ CHAT</b>", styles["VN"]))
    story.append(Spacer(1, 12))

    for m in logs:
        role = "Người dùng" if m["role"] == "user" else "Trợ lý"
        story.append(
            Paragraph(f"<b>{role}:</b><br/>{m['content']}", styles["VN"])
        )
        story.append(Spacer(1, 8))

    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="lich_su_chat.pdf",
        mimetype="application/pdf"
    )

# =====================================================
# HOME
# =====================================================

@app.route("/")
def index():
    session_id = get_session_id()

    resp = make_response(
        render_template(
            "index.html",
            HOTLINE=HOTLINE,
            BUILDER=BUILDER_NAME
        )
    )

    resp.set_cookie(
        "sid",
        session_id,
        httponly=True,
        samesite="Lax"
    )

    return resp

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        debug=False
    )
