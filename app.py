# ==============================
# app.py – CLEAN FINAL VERSION
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
    cur.execute("""CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created_at TEXT)""")
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
        c.execute("INSERT INTO sessions VALUES (?,?)", (sid, datetime.utcnow().isoformat()))
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

# ================= OPENAI =================
SYSTEM_PROMPT = f"""
Bạn là chuyên gia du lịch và văn hóa Việt Nam.

QUY TẮC:
- Nếu người dùng không nói địa điểm → mặc định {DEFAULT_CITY}
- Chỉ trả lời các chủ đề: du lịch, địa điểm, văn hóa, lịch sử, ẩm thực
- Văn phong rõ ràng, súc tích, có chiều sâu
- Không bịa dữ liệu

FORMAT:
📍 Giới thiệu
🏛 Lịch sử – Văn hóa
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
            "temperature": 0.5,
            "max_tokens": 900
        },
        timeout=60
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ================= MAP – GOOGLE MAPS (SERPAPI) =================
@app.route("/map-search")
def map_search():
    q = request.args.get("q", DEFAULT_CITY)
    r = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google_maps",
            "q": q,
            "hl": "vi",
            "gl": "vn",
            "api_key": SERPAPI_KEY
        },
        timeout=15
    )

    results = []
    for p in r.json().get("local_results", []):
        gps = p.get("gps_coordinates")
        if gps:
            results.append({
                "name": p.get("title"),
                "place_id": p.get("place_id"),
                "lat": gps["latitude"],
                "lng": gps["longitude"],
                "address": p.get("address"),
                "rating": p.get("rating"),
                "thumbnail": p.get("thumbnail")
            })
    return jsonify(results)

@app.route("/api/place_detail")
def place_detail():
    place_id = request.args.get("place_id")
    name = request.args.get("name", DEFAULT_CITY)

    r = requests.get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google_maps",
            "place_id": place_id,
            "hl": "vi",
            "gl": "vn",
            "api_key": SERPAPI_KEY
        },
        timeout=15
    )

    p = r.json().get("place_results", {})
    title = p.get("title", name)

    return jsonify({
        "name": title,
        "address": p.get("address"),
        "rating": p.get("rating"),
        "hours": p.get("hours"),
        "image": p.get("photos", [{}])[0].get("image"),
        "culture": f"Văn hóa địa phương tại {title} phản ánh rõ nét đời sống và tín ngưỡng Việt Nam.",
        "food": f"Ẩm thực {title} nổi bật với các món ăn mang bản sắc vùng miền."
    })

# ================= CHAT =================
@app.route("/chat", methods=["POST"])
def chat():
    sid = get_session()
    msg = request.json.get("msg", "").strip()
    if not msg:
        return jsonify({"error": "empty"}), 400

    save_msg(sid, "user", msg)
    msgs = history(sid)
    reply = ask_gpt(msgs)
    save_msg(sid, "assistant", reply)

    return jsonify({"reply": reply})

# ================= PDF =================
def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2*cm, 1.2*cm, f"{BUILDER_NAME} | {HOTLINE}")
    canvas.restoreState()

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    sid = request.cookies.get("sid")
    logs = history(sid)

    buf = io.BytesIO()
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(app.static_folder, "DejaVuSans.ttf")))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("VN", fontName="DejaVu", fontSize=11, leading=14))

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm)
    story = [Paragraph("<b>LỊCH SỬ CHAT</b>", styles["VN"]), Spacer(1, 12)]

    for m in logs:
        role = "Người dùng" if m["role"] == "user" else "Trợ lý"
        story.append(Paragraph(f"<b>{role}:</b> {m['content']}", styles["VN"]))
        story.append(Spacer(1, 8))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0)

    return send_file(buf, as_attachment=True, download_name="chat.pdf", mimetype="application/pdf")

# ================= HOME =================
@app.route("/")
def index():
    sid = get_session()
    r = make_response(render_template("index.html", HOTLINE=HOTLINE, BUILDER=BUILDER_NAME))
    r.set_cookie("sid", sid, httponly=True, samesite="Lax")
    return r

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

