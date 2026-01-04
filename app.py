import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF
import requests
from PIL import Image
from io import BytesIO

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")  # Key Serper.dev của bạn
DB_PATH = "chat_history.db"

# Prompt chỉ tập trung text chi tiết (images/video sẽ lấy realtime bằng Serper)
SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch Việt Nam. Trả về JSON chỉ có text chi tiết (>1200 từ), hấp dẫn, cấu trúc rõ ràng với markdown.

Cấu trúc JSON:
{
  "text": "# [Tên địa danh]\\n\\n[Mô tả mở đầu]\\n\\n## ⏳ Lịch sử hình thành\\n[chi tiết]\\n\\n## 🎭 Văn hóa đặc trưng\\n[chi tiết]\\n\\n## 🍲 Ẩm thực tiêu biểu\\n[chi tiết]\\n\\n## 📅 Lịch trình gợi ý\\n[chi tiết]\\n\\n### 🎥 Video khám phá thực tế\\n[Mô tả ngắn]\\n\\n### 💡 Gợi ý tiếp theo:\\n- Gợi ý 1\\n- Gợi ý 2..."
}

Nội dung sống động, chính xác, như hướng dẫn viên thực thụ. Chỉ trả về JSON thuần!
"""

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

def search_serper_images(query, num=12):
    if not SERPER_API_KEY:
        return []
    url = "https://google.serper.dev/images"
    payload = json.dumps({"q": query + " Vietnam travel site:pexels.com OR site:unsplash.com OR site:wikimedia.org", "num": num, "gl": "vn"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            images = []
            for item in data.get('images', [])[:num]:
                if 'imageUrl' in item or 'link' in item:
                    url_img = item.get('imageUrl') or item.get('link')
                    images.append({"url": url_img, "caption": item.get('title', 'Hình ảnh đẹp về ' + query)})
            return images
    except:
        pass
    return []

def search_serper_videos(query, num=6):
    if not SERPER_API_KEY:
        return []
    url = "https://google.serper.dev/videos"
    payload = json.dumps({"q": query + " Vietnam travel 2023 OR 2024 OR 2025 OR 2026", "num": num, "gl": "vn"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            videos = []
            for item in data.get('videos', [])[:num]:
                if 'link' in item and 'youtube.com' in item['link']:
                    videos.append(item['link'])
            return videos
    except:
        pass
    return []

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=365*24*3600)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg:
        return jsonify({"text": "Vui lòng nhập câu hỏi!", "images": [], "youtube_links": [], "suggestions": []})

    client = Groq(api_key=GROQ_API_KEY)
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            temperature=0.7,
            max_tokens=4096,
            response_format={"type": "json_object"}
        )
        ai_text = json.loads(completion.choices[0].message.content).get("text", "Xin lỗi, có lỗi khi xử lý.")
    except Exception as e:
        ai_text = f"Lỗi Groq: {str(e)}"

    # Extract địa danh chính từ msg để search realtime
    location = msg.lower().replace("tại", "").replace("về", "").replace("du lịch", "").strip()
    if not location:
        location = "Việt Nam"

    # Search realtime images + videos bằng Serper.dev
    images = search_serper_images(location, 12)
    youtube_links = search_serper_videos(location, 6)

    # Suggestions từ text (extract đơn giản)
    suggestions = []
    if "Gợi ý tiếp theo" in ai_text:
        sugg_part = ai_text.split("Gợi ý tiếp theo:")[1] if len(ai_text.split("Gợi ý tiếp theo:")) > 1 else ""
        for line in sugg_part.split("\n"):
            if line.strip().startswith("-"):
                suggestions.append(line.strip()[1:].strip())

    ai_data = {
        "text": ai_text,
        "images": images,
        "youtube_links": youtube_links,
        "suggestions": suggestions or ["Lịch trình chi tiết hơn?", "Quán ăn ngon?", "Khách sạn đẹp?"]
    }

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))

    return jsonify(ai_data)

# Các route khác giữ nguyên như trước (history, export_pdf, clear_history)
# (Copy từ bản cũ, chỉ sửa nhỏ export_pdf để dùng images realtime)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        for r in rows:
            content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
            res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    # Giữ nguyên bản fix font trước, dùng images realtime từ history
    # (copy từ bản cũ)

    # ... (giữ nguyên code export_pdf cũ)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
