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

# System prompt – yêu cầu nội dung rất chi tiết bằng tiếng Việt
SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM, Vũng Tàu và Bình Dương.
1. Nếu địa danh KHÔNG thuộc 3 nơi này hoặc không rõ ràng: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ thông tin du lịch về TP.HCM, Vũng Tàu và Bình Dương thôi nhé!"}
2. Nếu HỢP LỆ: Trả JSON {"is_valid": true, "text": "Nội dung chi tiết bằng tiếng Việt, dài trên 1200 từ, bao gồm các phần sau một cách logic và hấp dẫn: 
- Lịch sử hình thành và phát triển của địa danh
- Văn hóa đặc trưng, lễ hội, phong tục
- Con người địa phương, tính cách, lối sống
- Ẩm thực nổi bật, món ăn đặc sản, địa chỉ gợi ý
- Các địa điểm du lịch chính (check-in, tham quan)
- Hoạt động trải nghiệm (ăn chơi, nghỉ dưỡng, khám phá)
- Cách di chuyển, phương tiện, lộ trình gợi ý
- Lưu ý về thời tiết, an toàn, chi phí tham khảo
Viết sinh động, gần gũi, khuyến khích du lịch.", "suggestions": ["3 câu hỏi gợi ý liên quan đến địa danh vừa hỏi, bằng tiếng Việt"]}
Chỉ trả về JSON thuần túy, không thêm text thừa."""

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

def search_serper(query, search_type="images"):
    if not SERPER_API_KEY:
        return []
    
    q = query
    if search_type == "videos":
        q += " du lịch review thực tế Việt Nam -nhạc nền -karaoke -tin tức -scandal -youtube shorts"
    else:
        q += " du lịch Việt Nam hình ảnh đẹp thực tế địa danh"

    url = f"https://google.serper.dev/{search_type}"
    try:
        res = requests.post(
            url,
            headers={'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'},
            json={"q": q, "gl": "vn", "hl": "vi", "num": 10},
            timeout=12
        ).json()

        if search_type == "images":
            return [{"url": i.get('imageUrl'), "caption": i.get('title', 'Hình ảnh du lịch')} 
                    for i in res.get('images', [])[:6]]
        else:  # videos
            return [i.get('link') for i in res.get('videos', []) 
                    if 'youtube.com' in i.get('link', '').lower() or 'youtu.be' in i.get('link', '').lower()][:5]
    except Exception as e:
        print(f"Serper error: {e}")
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
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": msg}
            ],
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=4500
        )
        
        ai_res = json.loads(completion.choices[0].message.content)
        
        images = []
        videos = []
        if ai_res.get("is_valid", False):
            images = search_serper(msg, "images")
            videos = search_serper(msg, "videos")
        
        data = {
            "text": ai_res.get("text", "Không có nội dung trả lời."),
            "images": images,
            "youtube_links": videos,
            "suggestions": ai_res.get("suggestions", [
                "Du lịch Sài Gòn 1 ngày", 
                "Kinh nghiệm đi Vũng Tàu cuối tuần", 
                "Ẩm thực đặc sản Bình Dương"
            ])
        }
        
        now = datetime.now().strftime("%H:%M %d/%m/%Y")
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                        (sid, "user", msg, now))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                        (sid, "bot", json.dumps(data, ensure_ascii=False), now))
        
        return jsonify(data)
    
    except Exception as e:
        print(f"Groq error: {e}")
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "images": [], "youtube_links": []})

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (sid,)
        ).fetchall()
        
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
    
    # Load font DejaVuSans (phải đặt file trong thư mục static/)
    font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", "", 12)
    else:
        pdf.set_font("Arial", "", 12)  # fallback nếu không có font
    
    pdf.cell(0, 10, "LỊCH TRÌNH DU LỊCH - VIET NAM TRAVEL AI GUIDE", ln=True, align="C")
    pdf.ln(10)
    
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (sid,)
        ).fetchall()
        
        for role, content in rows:
            if role == "bot":
                try:
                    data = json.loads(content)
                    text = data.get("text", "")
                except:
                    text = content
            else:
                text = content
            
            prefix = "Bạn: " if role == "user" else "AI Guide: "
            pdf.multi_cell(0, 8, f"{prefix}{text}")
            pdf.ln(6)
    
    output_path = "lich_trinh_du_lich.pdf"
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
