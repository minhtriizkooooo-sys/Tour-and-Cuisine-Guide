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

# --- THAY KEY THẬT CỦA BẠN VÀO ĐÂY ---
OPENAI_API_KEY = "sk-..." 
SERPAPI_KEY = "..."

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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    msg = data.get("msg", "")
    sid = data.get("sid", "default")
    
    # 1. SERPAPI - Lấy dữ liệu thật
    search = GoogleSearch({"q": msg, "api_key": SERPAPI_KEY, "hl": "vi"})
    res = search.get_dict()
    context = " ".join([o.get("snippet", "") for o in res.get("organic_results", [])[:3]])
    images = [{"url": i.get("thumbnail"), "caption": i.get("title")} for i in res.get("inline_images", [])[:4]]

    # 2. OPENAI - Trả lời
    r = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": f"Dữ liệu thật: {context}. Hãy trả lời chi tiết."},
                {"role": "user", "content": msg + " [SUGGESTIONS] gợi ý 1|gợi ý 2|gợi ý 3 [/SUGGESTIONS]"}
            ]
        })
    
    full_reply = r.json()["choices"][0]["message"]["content"]
    reply_text = full_reply.split("[SUGGESTIONS]")[0].strip()
    
    # Lưu DB
    with db_conn() as conn:
        conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (sid, "user", msg))
        conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?,?,?)", (sid, "bot", reply_text))
        conn.commit()

    return jsonify({"reply": reply_text, "images": images})

@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    sid = request.json.get("sid")
    with db_conn() as conn:
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id=?", (sid,)).fetchall()
    buf = io.BytesIO()
    try: pdfmetrics.registerFont(TTFont("DejaVu", "static/DejaVuSans.ttf"))
    except: pass
    doc = SimpleDocTemplate(buf, pagesize=A4)
    story = [Paragraph(f"<b>{r['role']}:</b> {r['content']}", ParagraphStyle('VN', fontName='DejaVu' if 'DejaVu' in pdfmetrics.getRegisteredFontNames() else 'Helvetica', fontSize=10, leading=14)) for r in rows]
    doc.build(story)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="history.pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
