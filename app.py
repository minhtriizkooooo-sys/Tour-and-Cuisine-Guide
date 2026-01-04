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
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"

# Prompt yêu cầu text sạch, không có ### thừa cho video/gợi ý
SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch Việt Nam. Trả về JSON chỉ chứa text chi tiết (>1200 từ), hấp dẫn, cấu trúc rõ ràng với markdown.

Cấu trúc JSON:
{
  "text": "# [Tên địa danh]\\n\\n[Mô tả mở đầu sống động]\\n\\n## ⏳ Lịch sử hình thành\\n[chi tiết]\\n\\n## 🎭 Văn hóa đặc trưng\\n[chi tiết]\\n\\n## 🍲 Ẩm thực tiêu biểu\\n[chi tiết]\\n\\n## 📅 Lịch trình gợi ý\\n[chi tiết lịch trình]\\n\\nGợi ý tiếp theo (viết dạng danh sách - không dùng tiêu đề ###):\\n- Gợi ý 1\\n- Gợi ý 2..."
}

Nội dung tự nhiên, mượt mà, KHÔNG dùng bất kỳ tiêu đề ### nào cho phần video hoặc gợi ý. Chỉ trả về JSON thuần!
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

# Ưu tiên ảnh chất lượng cao
def search_serper_images(query, num=5):
    if not SERPER_API_KEY:
        return []
    url = "https://google.serper.dev/images"
    payload = json.dumps({
        "q": f"{query} du lịch Việt Nam chất lượng cao đẹp",
        "num": num,
        "gl": "vn"
    })
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=12)
        if response.status_code == 200:
            results = response.json().get('images', [])[:num]
            return [{"url": item.get('imageUrl') or item.get('link', ''), "caption": item.get('title', f"Ảnh đẹp về {query}")} for item in results if item.get('imageUrl') or item.get('link')]
    except Exception as e:
        print(f"Serper images error: {e}")
    return []

# ƯU TIÊN VIDEO TIẾNG VIỆT - tìm kiếm nghiêm ngặt
def search_serper_videos(query, num=5):
    if not SERPER_API_KEY:
        return []
    url = "https://google.serper.dev/videos"
    payload = json.dumps({
        "q": f"{query} du lịch Việt Nam tiếng Việt vlog OR review OR hướng dẫn OR khám phá 2023 OR 2024 OR 2025 OR 2026 site:youtube.com",
        "num": num * 2,  # Lấy gấp đôi để lọc tốt hơn
        "gl": "vn"
    })
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=12)
        if response.status_code == 200:
            results = response.json().get('videos', [])
            videos = []
            for item in results:
                link = item.get('link', '')
                title = item.get('title', '').lower()
                # Ưu tiên video tiếng Việt (có từ khóa tiếng Việt phổ biến)
                if ('youtube.com' in link or 'youtu.be' in link) and any(keyword in title for keyword in ["du lịch", "đà lạt", "hội an", "phú quốc", "việt nam", "vlog", "review", "khám phá", "hướng dẫn"]):
                    videos.append(link)
                if len(videos) >= num:
                    break
            return videos[:num]
    except Exception as e:
        print(f"Serper videos error: {e}")
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
        ai_text = json.loads(completion.choices[0].message.content).get("text", "Xin lỗi, có lỗi.")
    except Exception as e:
        ai_text = f"Lỗi Groq: {str(e)}"

    # Trích xuất địa danh chính xác hơn
    words = msg.lower().split()
    location_words = [w for w in words if w not in ["tại", "ở", "về", "du lịch", "review", "chi tiết", "cho", "tôi", "hỏi", "về"]]
    location = " ".join(location_words).strip() or "Việt Nam"

    # Lấy 5 ảnh + 5 video (ưu tiên tiếng Việt)
    images = search_serper_images(location, 5)
    youtube_links = search_serper_videos(location, 5)

    # Extract gợi ý từ text (AI viết dạng danh sách -)
    suggestions = []
    lines = ai_text.split("\n")
    collecting = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Gợi ý tiếp theo") or "gợi ý" in stripped.lower():
            collecting = True
            continue
        if collecting and stripped.startswith("-"):
            suggestions.append(stripped[1:].strip())
        elif collecting and stripped and not stripped.startswith("-"):
            break
    if len(suggestions) < 3:
        suggestions = ["Lịch trình chi tiết 4 ngày tự túc?", "Top quán ăn ngon nhất?", "Khách sạn view đẹp giá tốt?", "Địa điểm check-in mới nhất?", "Mùa nào đẹp nhất để đi?"]

    ai_data = {
        "text": ai_text,
        "images": images,
        "youtube_links": youtube_links,
        "suggestions": suggestions
    }

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))

    return jsonify(ai_data)

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
    sid = request.cookies.get("session_id")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=13)
    else:
        pdf.set_font("Arial", size=13)

    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 15, "VIETNAM TRAVEL AI GUIDE 2026", ln=True, align='C')
    pdf.ln(10)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()

        for r in rows:
            if r['role'] == 'user':
                pdf.set_font("DejaVu", size=12) if os.path.exists(font_path) else pdf.set_font("Arial", size=12)
                pdf.set_text_color(0, 100, 200)
                pdf.multi_cell(0, 8, f"Bạn: {r['content']}")
                pdf.ln(6)
            else:
                try:
                    data = json.loads(r['content'])
                    text = data.get('text', '').strip()
                    images = data.get('images', [])
                    youtube_links = data.get('youtube_links', [])
                except:
                    text = r['content']
                    images = []
                    youtube_links = []

                if text:
                    pdf.set_font("DejaVu", size=11) if os.path.exists(font_path) else pdf.set_font("Arial", size=11)
                    pdf.set_text_color(0, 0, 0)
                    pdf.multi_cell(0, 7, text)
                    pdf.ln(8)

                # 5 ảnh trong PDF
                for img in images[:5]:
                    url = img['url']
                    caption = img.get('caption', 'Hình ảnh du lịch')
                    try:
                        response = requests.get(url, timeout=15)
                        if response.status_code == 200:
                            img_data = BytesIO(response.content)
                            Image.open(img_data)  # Kiểm tra ảnh hợp lệ
                            pdf.image(url, w=170)
                            pdf.set_font("DejaVu", size=9) if os.path.exists(font_path) else pdf.set_font("Arial", size=9)
                            pdf.multi_cell(0, 5, caption)
                            pdf.ln(8)
                    except:
                        continue

                # 5 video tiếng Việt trong PDF
                if youtube_links:
                    pdf.set_font("DejaVu", size=11) if os.path.exists(font_path) else pdf.set_font("Arial", size=11)
                    pdf.set_text_color(200, 0, 0)
                    pdf.cell(0, 8, "Video khám phá thực tế bằng tiếng Việt:", ln=True)
                    pdf.set_font("DejaVu", size=10) if os.path.exists(font_path) else pdf.set_font("Arial", size=10)
                    pdf.set_text_color(0, 0, 180)
                    for link in youtube_links[:5]:
                        pdf.cell(0, 7, link, ln=True, link=link)
                    pdf.ln(10)

    pdf_file = "Lich_Trinh_Du_Lich_2026.pdf"
    pdf.output(pdf_file)
    return send_file(pdf_file, as_attachment=True, download_name="Lich_Trinh_Viet_Nam_2026.pdf")

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
