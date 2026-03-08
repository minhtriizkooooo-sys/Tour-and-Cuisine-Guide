import os, uuid, sqlite3, json, requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF
from PIL import Image
from io import BytesIO
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro")
CORS(app)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
# System Prompt: Cứng rắn với địa danh ngoài phạm vi, và đảm bảo nội dung đầy đủ
SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM, Vũng Tàu và Bình Dương.
1. Nếu địa danh KHÔNG thuộc 3 nơi này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ TP.HCM, Vũng Tàu và Bình Dương."}
2. Nếu HỢP LỆ: Trả JSON {"is_valid": true, "text": "# [Tên]\\n... nội dung chi tiết >1200 từ bao gồm đầy đủ: lịch sử hình thành và phát triển địa danh, văn hóa đặc trưng, con người địa phương, ẩm thực nổi bật, các địa điểm du lịch chính, hoạt động trải nghiệm, lưu ý khi tham quan... Mô tả sống động, hấp dẫn bằng tiếng Việt thuần túy.", "suggestions": ["Gợi ý câu hỏi liên quan 1", "Gợi ý câu hỏi liên quan 2", "Gợi ý câu hỏi liên quan 3"]}
KHÔNG dùng ### cho video/gợi ý. Chỉ trả JSON thuần."""
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()
def search_serper(query, type="images"):
    if not SERPER_API_KEY: return []
    # Tinh chỉnh query để đảm bảo liên quan: Thêm từ khóa cụ thể về địa danh, du lịch thực tế, loại trừ rác
    q = f"{query} du lịch Việt Nam review thực tế lịch sử văn hóa ẩm thực con người -nhạc -karaoke -news -scandal -bán hàng" if type == "videos" else f"{query} du lịch Việt Nam chất lượng cao hình ảnh thực tế địa danh"
    url = f"https://google.serper.dev/{type}"
    try:
        res = requests.post(url, headers={'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'},
                            json={"q": q, "gl": "vn", "hl": "vi", "num": 10}, timeout=10).json()
        if type == "images":
            return [{"url": i.get('imageUrl'), "caption": i.get('title')} for i in res.get('images', [])[:5] if 'vietnam' in i.get('title', '').lower() or 'tp hcm' in i.get('title', '').lower() or 'vung tau' in i.get('title', '').lower() or 'binh duong' in i.get('title', '').lower()]
        return [i.get('link') for i in res.get('videos', []) if 'yout' in i.get('link', '') and ('du lịch' in i.get('title', '').lower() or 'review' in i.get('title', '').lower())][:5]
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
       
        # Nếu địa danh hợp lệ mới tìm ảnh/video, ngược lại để trống
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
    # Sử dụng font DejaVuSans để hỗ trợ tiếng Việt
    sid = request.cookies.get("session_id")
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'static/DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', '', 12)
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ?", (sid,)).fetchall()
        for role, content in rows:
            text = json.loads(content).get('text') if role == 'bot' else content
            pdf.multi_cell(0, 10, f"{'AI' if role=='bot' else 'Bạn'}: {text.encode('latin1', 'replace').decode('latin1')}")
    pdf.output("lich_trinh.pdf")
    return send_file("lich_trinh.pdf", as_attachment=True)
@app.route("/clear_history", methods=["POST"])
def clear_history():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (request.cookies.get("session_id"),))
    return jsonify({"status": "ok"})
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
