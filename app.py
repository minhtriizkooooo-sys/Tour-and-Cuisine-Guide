import os
import uuid
import sqlite3
import json
import requests
from datetime import datetime
import pytz
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY_TCG")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (Thành phố Hồ Chí Minh), bao gồm mọi quận/huyện, tòa nhà biểu tượng, landmark, trung tâm thương mại, khu đô thị... (ví dụ: Landmark 81, Bitexco Financial Tower, Saigon Marina, IFC One Saigon, Crescent Mall, phố đi bộ Nguyễn Huệ, chợ Bến Thành, v.v.).

Nếu địa danh, tòa nhà, khu vực KHÔNG thuộc TP.HCM → Trả ngay JSON:
{"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ thông tin du lịch tại TP.HCM thôi nhé!"}

Nếu HỢP LỆ: Trả về JSON chi tiết (>2200 từ), dùng markdown phong phú:
- ## Lịch sử hình thành & phát triển (quá khứ → hiện tại → dự báo 2026-2030)
- ## Con người, văn hóa, lối sống đặc trưng
- ## Ẩm thực nổi bật (8-12 món + địa chỉ cụ thể + giá tham khảo 2026)
- ## Lịch trình du lịch chi tiết (1 ngày / 2 ngày / 3 ngày + thời gian, phương tiện, chi phí ước tính)
- ## Tầm nhìn tương lai & dự án phát triển khu vực này đến 2026-2030

Cuối cùng thêm mảng gợi ý:
"suggestions": ["Câu hỏi hay 1", "Câu hỏi hay 2", "Câu hỏi hay 3"]

Chỉ trả JSON thuần túy, không thêm text thừa.
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

def search_serper_images(query):
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": f"{query} TP.HCM du lịch thực tế 2025 2026"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        return [{"url": i.get("imageUrl"), "caption": i.get("title", query)} for i in data.get("images", [])[:8]]
    except:
        return []

def search_serper_youtube(query):
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/videos"
        # Tăng độ sát: bắt buộc có tiếng Việt + trải nghiệm + địa danh
        search_q = f"{query} du lịch TP.HCM trải nghiệm thực tế tiếng Việt review 2025 2026 -english -sub"
        payload = json.dumps({"q": search_q})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=12)
        videos = resp.json().get("videos", [])
        # Lọc thêm: chỉ lấy link youtube và có từ "tiếng Việt" hoặc review trong snippet nếu có
        filtered = []
        for v in videos:
            link = v.get("link", "")
            if "youtube" not in link.lower():
                continue
            title = v.get("title", "").lower()
            snippet = v.get("snippet", "").lower()
            if "tiếng việt" in title or "tiếng việt" in snippet or "review" in title or "trải nghiệm" in title:
                filtered.append(link)
        return filtered[:4]
    except:
        return []

def search_serper_future_images():
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": "TP.HCM phát triển tương lai 2026 2027 2030 hình ảnh dự án thực tế đô thị cao tầng"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        return [{"url": i.get("imageUrl"), "caption": i.get("title", "Tầm nhìn TP.HCM tương lai")} for i in data.get("images", [])[:7]]
    except:
        return []

def search_serper_future_youtube():
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/videos"
        payload = json.dumps({"q": "tương lai TP.HCM 2026 2027 2030 phát triển đô thị hạ tầng video tiếng Việt review dự án"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=12)
        videos = resp.json().get("videos", [])
        filtered = []
        for v in videos:
            link = v.get("link", "")
            if "youtube" not in link.lower():
                continue
            title = v.get("title", "").lower()
            snippet = v.get("snippet", "").lower()
            if "tiếng việt" in title or "tiếng việt" in snippet or "dự án" in title or "phát triển" in title:
                filtered.append(link)
        return filtered[:3]
    except:
        return []

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=31536000)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg:
        return jsonify({"error": "Empty message"})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            response_format={"type": "json_object"}
        )
        ai_res = json.loads(completion.choices[0].message.content)

        if ai_res.get("is_valid", False):
            clean_query = msg.replace("Thông tin du lịch chi tiết về", "").replace("tại TP.HCM năm 2026", "").strip()
            ai_res["images"] = search_serper_images(clean_query or msg)
            ai_res["youtube_links"] = search_serper_youtube(clean_query or msg)
            ai_res["future_images"] = search_serper_future_images()
            ai_res["future_youtube_links"] = search_serper_future_youtube()

        now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, now_vn))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_res), now_vn))

        return jsonify(ai_res)

    except Exception as e:
        return jsonify({"text": f"Lỗi: {str(e)}", "is_valid": False})

# Các route còn lại giữ nguyên như trước (history, clear_history, export_pdf)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()
    formatted = []
    for r, c in rows:
        content = json.loads(c) if r == "bot" else c
        formatted.append({"role": r, "content": content})
    return jsonify(formatted)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()
    if not rows: return "Không có dữ liệu."
    pdf = FPDF()
    pdf.add_page()
    font_path = os.path.join("static", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=11)
    else:
        pdf.set_font("Arial", size=11)
    now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    pdf.cell(200, 10, txt="THÔNG TIN DU LỊCH TP.HCM 2026", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Xuất lúc: {now_vn}", ln=True, align='C')
    pdf.ln(10)
    for role, content in rows:
        label = "BẠN: " if role == "user" else "AI: "
        if role == "bot":
            try:
                data = json.loads(content)
                text = data.get("text", "")
                pdf.multi_cell(0, 8, txt=f"{label}\n{text}")
            except:
                pdf.multi_cell(0, 8, txt=f"{label}{content}")
        else:
            pdf.multi_cell(0, 8, txt=f"{label}{content}")
        pdf.ln(6)
    path = f"history_{sid[:12]}.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
