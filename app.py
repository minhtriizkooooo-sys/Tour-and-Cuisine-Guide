import os, uuid, sqlite3, json, requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"

# System Prompt: Cứng rắn với địa danh ngoài phạm vi
SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM, Vũng Tàu và Bình Dương.
1. Nếu địa danh KHÔNG thuộc 3 nơi này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ TP.HCM, Vũng Tàu và Bình Dương."}
2. Nếu HỢP LỆ: Trả JSON {"is_valid": true, "text": "# [Tên]\\n... nội dung chi tiết >1200 từ...", "suggestions": ["Câu hỏi 1", "Câu hỏi 2"]}
KHÔNG dùng ### cho video/gợi ý. Chỉ trả JSON thuần."""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def search_serper(query, type="images"):
    if not SERPER_API_KEY: return []
    q = f"{query} du lịch review thực tế -nhạc -karaoke -news -scandal" if type == "videos" else f"{query} du lịch chất lượng cao"
    url = f"https://google.serper.dev/{type}"
    try:
        res = requests.post(url, headers={'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}, 
                            json={"q": q, "gl": "vn", "hl": "vi", "num": 10}, timeout=10).json()
        if type == "images":
            return [{"url": i.get('imageUrl'), "caption": i.get('title')} for i in res.get('images', [])[:5]]
        return [i.get('link') for i in res.get('videos', []) if 'yout' in i.get('link', '')][:5]
    except: return []

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
    client = Groq(api_key=GROQ_API_KEY)
    
    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            response_format={"type": "json_object"}
        )
        ai_res = json.loads(chat_completion.choices[0].message.content)
        
        images, videos = (search_serper(msg, "images"), search_serper(msg, "videos")) if ai_res.get("is_valid") else ([], [])
        
        data = {"text": ai_res.get("text"), "images": images, "youtube_links": videos, 
                "suggestions": ai_res.get("suggestions", ["Du lịch Sài Gòn", "Chơi gì ở Vũng Tàu", "Bình Dương có gì đẹp?"])}
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)", (sid, "user", msg, datetime.now().strftime("%H:%M")))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)", (sid, "bot", json.dumps(data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
        return jsonify(data)
    except Exception as e:
        return jsonify({"text": f"Lỗi: {str(e)}", "images": [], "youtube_links": []})

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        return jsonify([{"role": r['role'], "content": json.loads(r['content']) if r['role']=='bot' else r['content']} for r in rows])

@app.route("/export_pdf")
def export_pdf():
    try:
        sid = request.cookies.get("session_id")
        pdf = FPDF()
        pdf.add_page()

        # ĐĂNG KÝ FONT ĐỂ ĐỌC TIẾNG VIỆT
        font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
        if not os.path.exists(font_path):
            return "Lỗi: Không tìm thấy file font DejaVuSans.ttf trong thư mục static", 500
        
        pdf.add_font('DejaVu', '', font_path, uni=True)
        pdf.set_font('DejaVu', '', 14)

        # Tiêu đề PDF
        pdf.cell(0, 10, txt="LỊCH TRÌNH DU LỊCH CHI TIẾT 2026", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font('DejaVu', '', 11)

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
            
            for row in rows:
                role_label = "BẠN: " if row['role'] == 'user' else "AI: "
                raw_content = row['content']
                
                # Trích xuất text từ JSON của Bot
                if row['role'] == 'bot':
                    try:
                        data = json.loads(raw_content)
                        text = data.get('text', '')
                    except:
                        text = raw_content
                else:
                    text = raw_content

                # In Vai trò
                pdf.set_text_color(200, 0, 0) if row['role'] == 'user' else pdf.set_text_color(0, 100, 0)
                pdf.write(8, role_label)
                
                # In Nội dung (Làm sạch ký tự Markdown cơ bản)
                pdf.set_text_color(0, 0, 0)
                clean_text = text.replace('**', '').replace('#', '')
                pdf.multi_cell(0, 8, txt=clean_text)
                pdf.ln(5)

        output_path = "lich_trinh_du_lich.pdf"
        pdf.output(output_path)
        return send_file(output_path, as_attachment=True)

    except Exception as e:
        return f"Lỗi hệ thống PDF: {str(e)}", 500

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
