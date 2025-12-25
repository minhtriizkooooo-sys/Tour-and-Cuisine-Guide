import os
import io
import uuid
import sqlite3
import requests
import wikipedia
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template,
    make_response, send_file
)
from flask_cors import CORS

# PDF (Unicode)
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------- CONFIG ----------------
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
DB_PATH = os.getenv("SQLITE_PATH", "chat_history.db")

HOTLINE = os.getenv("HOTLINE", "+84-908-08-3566")
BUILDER_NAME = os.getenv("BUILDER_NAME", "Vietnam Travel AI – Tours and Cuisine Guide - Lại Nguyễn Minh Trí")

DEFAULT_CITY = "Thành phố Hồ Chí Minh"

# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question TEXT,
            created_at TEXT
        )
    """)
    db.commit()
    db.close()

init_db()

# ---------------- SESSION ----------------
def ensure_session():
    sid = request.cookies.get("session_id")
    if not sid:
        sid = str(uuid.uuid4())
        db = get_db()
        db.execute(
            "INSERT OR IGNORE INTO sessions VALUES (?,?)",
            (sid, datetime.utcnow().isoformat())
        )
        db.commit()
        db.close()
    return sid

def save_message(sid, role, content):
    db = get_db()
    db.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
        (sid, role, content, datetime.utcnow().isoformat())
    )
    db.commit()
    db.close()

def fetch_history(sid):
    if not sid:
        return []
    db = get_db()
    rows = db.execute(
        "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id",
        (sid,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

def save_suggestions(sid, questions):
    db = get_db()
    for q in questions:
        db.execute(
            "INSERT INTO suggestions (session_id, question, created_at) VALUES (?,?,?)",
            (sid, q, datetime.utcnow().isoformat())
        )
    db.commit()
    db.close()

def fetch_suggestions(sid):
    if not sid:
        return []
    db = get_db()
    rows = db.execute(
        "SELECT question FROM suggestions WHERE session_id=?",
        (sid,)
    ).fetchall()
    db.close()
    return [r["question"] for r in rows]

# ---------------- OPENAI ----------------
SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch Việt Nam.

QUY TẮC:
- Nếu người dùng KHÔNG nêu địa điểm → mặc định TP. Hồ Chí Minh
- Nếu KHÔNG liên quan du lịch → xin lỗi lịch sự

FORMAT:
📍 Giới thiệu
🗓 Lịch trình
🍜 Ẩm thực
💰 Chi phí

Trả lời bằng tiếng Việt.
"""

def call_openai(user_msg):
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.6,
            "max_tokens": 800
        },
        timeout=60
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def generate_suggestions(question, answer):
    prompt = f"""
Dựa trên câu hỏi và câu trả lời sau, hãy gợi ý 3 câu hỏi tiếp theo.
Chỉ liệt kê danh sách.

Câu hỏi: {question}
Trả lời: {answer}
"""
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Bạn là trợ lý gợi ý câu hỏi."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 200
        },
        timeout=60
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return [x.strip("- ").strip() for x in text.splitlines() if x.strip()]

# ---------------- SERPAPI IMAGE / VIDEO ----------------
def search_images(query):
    if not SERPAPI_KEY:
        return []
    r = requests.get(
        "https://serpapi.com/search.json",
        params={
            "q": query,
            "tbm": "isch",
            "hl": "vi",
            "gl": "vn",
            "api_key": SERPAPI_KEY
        },
        timeout=10
    )
    return [
        {"url": i.get("original"), "caption": i.get("title")}
        for i in r.json().get("images_results", [])
    ]

def search_youtube(query):
    if not SERPAPI_KEY:
        return []
    r = requests.get(
        "https://serpapi.com/search.json",
        params={
            "q": query,
            "tbm": "vid",
            "hl": "vi",
            "gl": "vn",
            "api_key": SERPAPI_KEY
        },
        timeout=10
    )
    return [
        v.get("link")
        for v in r.json().get("video_results", [])
        if "youtube" in v.get("link", "")
    ]

# ---------------- WIKIPEDIA ----------------
def wiki_summary(place):
    try:
        wikipedia.set_lang("vi")
        return wikipedia.summary(place, sentences=5)
    except:
        try:
            wikipedia.set_lang("en")
            return wikipedia.summary(place, sentences=4)
        except:
            return "Chưa có dữ liệu lịch sử chi tiết từ Wikipedia."

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    sid = ensure_session()
    resp = make_response(render_template(
        "index.html",
        HOTLINE=HOTLINE,
        BUILDER=BUILDER_NAME
    ))
    resp.set_cookie("session_id", sid, httponly=True, samesite="Lax")
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = ensure_session()
    msg = (request.json or {}).get("msg", "").strip()
    if not msg:
        return jsonify({"error": "empty"}), 400

    save_message(sid, "user", msg)
    reply = call_openai(msg)
    save_message(sid, "bot", reply)

    suggestions = generate_suggestions(msg, reply)
    save_suggestions(sid, suggestions)

    images = search_images(msg)
    videos = search_youtube(msg)

    return jsonify({
        "reply": reply,
        "images": images,
        "videos": videos,
        "suggestions": suggestions
    })

@app.route("/history")
def history():
    sid = request.cookies.get("session_id")
    return jsonify({"history": fetch_history(sid)})

# ---------------- MAP SEARCH ----------------
@app.route("/map-search")
def map_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

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
                "hours": p.get("hours")
            })
    return jsonify(results)

# ---------------- PLACE DETAIL ----------------
@app.route("/api/place_detail")
def place_detail():
    place_id = request.args.get("place_id")
    name_param = request.args.get("name", "").strip()

    if place_id:
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
        data = r.json()
    else:
        query = name_param or DEFAULT_CITY
        r = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_maps",
                "q": query,
                "hl": "vi",
                "gl": "vn",
                "api_key": SERPAPI_KEY
            },
            timeout=15
        )
        data = r.json()

    place = data.get("place_results", {})

    name = place.get("title", name_param or DEFAULT_CITY)
    history = wiki_summary(name)

    return jsonify({
        "name": name,
        "address": place.get("address", ""),
        "rating": place.get("rating", "N/A"),
        "reviews": place.get("reviews", "N/A"),
        "hours": place.get("hours", "Không rõ"),
        "image": place.get("photos", [{}])[0].get("image", ""),
        "history": history,
        "culture": f"Văn hóa và con người tại {name} mang đậm bản sắc địa phương.",
        "food": f"Ẩm thực {name} nổi bật với nhiều món ăn đặc trưng vùng miền."
    })

# ---------------- PDF ----------------
def pdf_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2*cm, 1.2*cm, f"{BUILDER_NAME} | Hotline: {HOTLINE}")
    canvas.drawRightString(A4[0]-2*cm, 1.2*cm, f"Trang {doc.page}")
    canvas.restoreState()

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    sid = request.cookies.get("session_id")
    history = fetch_history(sid)

    buffer = io.BytesIO()
    font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
    pdfmetrics.registerFont(TTFont("DejaVu", font_path))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("VN", fontName="DejaVu", fontSize=11, leading=14))

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2.5*cm
    )

    story = [Paragraph("<b>LỊCH SỬ CHAT</b>", styles["VN"]), Spacer(1, 12)]

    for h in history:
        label = "NGƯỜI DÙNG" if h["role"] == "user" else "TRỢ LÝ"
        story.append(Paragraph(f"<b>{label}:</b> {h['content']}", styles["VN"]))
        story.append(Spacer(1, 8))

    doc.build(story, onFirstPage=pdf_footer, onLaterPages=pdf_footer)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="lich_su_chat.pdf",
        mimetype="application/pdf"
    )

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
