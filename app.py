import os
import uuid
import sqlite3
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (bao gồm tất cả quận, huyện, địa danh nổi tiếng như Bitexco, Landmark 81, Chợ Bến Thành, Phố đi bộ Nguyễn Huệ, Nhà thờ Đức Bà, Bưu điện Thành phố, các tòa nhà cao tầng, khu vui chơi, quán ăn...), Vũng Tàu và Bình Dương.
1. Nếu địa danh KHÔNG thuộc 3 nơi này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ du lịch TP.HCM, Vũng Tàu và Bình Dương. Nếu là địa điểm trong TP.HCM, thử mô tả rõ hơn nhé!"}
2. Nếu HỢP LỆ: Trả JSON {"is_valid": true, "text": "Nội dung chi tiết bằng tiếng Việt, dài >1500 từ, có chiều sâu, cấu trúc rõ ràng và liên quan trực tiếp đến địa danh hỏi: 
- Lịch sử hình thành, phát triển qua các giai đoạn quan trọng, sự kiện nổi bật
- Văn hóa đặc trưng: lễ hội truyền thống, phong tục tập quán, di sản văn hóa
- Con người địa phương: tính cách, lối sống, thói quen sinh hoạt, cách tương tác với du khách
- Ẩm thực nổi bật: món ăn đặc sản, nguồn gốc, cách chế biến, địa chỉ quán ăn ngon gần đó
- Gợi ý du lịch chi tiết: địa điểm check-in gần, hoạt động trải nghiệm (ăn chơi, nghỉ dưỡng, khám phá), lộ trình mẫu 1-3 ngày, lưu ý thời tiết, an toàn, chi phí tham khảo, giờ mở cửa.
Viết hấp dẫn, sinh động, gần gũi, dựa trên kiến thức thực tế, khuyến khích du khách.", "suggestions": ["3 câu hỏi gợi ý liên quan sâu đến địa danh vừa hỏi, bằng tiếng Việt"]}
Chỉ trả JSON thuần, không thêm text ngoài."""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")

init_db()

def search_serper(query, search_type="images"):
    if not SERPER_API_KEY:
        return []
    
    base_q = f"{query} du lịch Việt Nam thực tế review chi tiết địa danh"
    if search_type == "videos":
        q = f"{query} du lịch review youtube trải nghiệm địa danh"
    else:
        q = f"{base_q} hình ảnh đẹp check-in thực tế địa danh"

    url = f"https://google.serper.dev/{search_type}"
    try:
        res = requests.post(
            url,
            headers={'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'},
            json={"q": q, "gl": "vn", "hl": "vi", "num": 25},
            timeout=15
        ).json()

        if search_type == "images":
            return [{"url": i.get('imageUrl'), "caption": i.get('title', 'Ảnh du lịch')} for i in res.get('images', [])[:10]]
        else:
            videos = []
            for i in res.get('videos', [])[:10]:
                link = i.get('link', '')
                if 'youtube.com' in link.lower() or 'youtu.be' in link.lower():
                    videos.append(link)
            print(f"[DEBUG Videos] Query: {q} → Found {len(videos)} videos")
            return videos
    except Exception as e:
        print(f"Serper error ({search_type}): {e}")
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
        return jsonify({"text": "Bạn chưa nhập gì cả...", "images": [], "youtube_links": []})

    client = Groq(api_key=GROQ_API_KEY)
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=4500
        )
        
        ai_res = json.loads(completion.choices[0].message.content)
        
        images, videos = [], []
        if ai_res.get("is_valid", False):
            images = search_serper(msg, "images")
            videos = search_serper(msg, "videos")
        
        data = {
            "text": ai_res.get("text", "Không có nội dung."),
            "images": images,
            "youtube_links": videos,
            "suggestions": ai_res.get("suggestions", ["Du lịch Landmark 81", "Review Vũng Tàu", "Bình Dương có gì chơi"])
        }
        
        now = datetime.now().strftime("%H:%M %d/%m/%Y")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)", (sid, "user", msg, now))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)", (sid, "bot", json.dumps(data, ensure_ascii=False), now))
        
        return jsonify(data)
    
    except Exception as e:
        print(f"Groq error: {e}")
        return jsonify({"text": f"Lỗi: {str(e)}", "images": [], "youtube_links": []})

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        history = []
        for r in rows:
            if r['role'] == 'bot':
                history.append({"role": "bot", "content": json.loads(r['content'])})
            else:
                history.append({"role": "user", "content": r['content']})
        return jsonify(history)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    pdf = FPDF()
    pdf.add_page()
    font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", "", 12)
    else:
        pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, "LỊCH TRÌNH DU LỊCH - VIET NAM TRAVEL AI", ln=True, align="C")
    pdf.ln(10)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        for role, content, created_at in rows:
            text = json.loads(content).get("text", "") if role == "bot" else content
            prefix = f"[{created_at}] {'Bạn' if role == 'user' else 'AI'}: "
            pdf.multi_cell(0, 8, f"{prefix}{text}")
            pdf.ln(6)
    output_path = "lich_trinh.pdf"
    pdf.output(output_path)
    return send_file(output_path, as_attachment=True, download_name="LichTrinhDuLich.pdf")

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
