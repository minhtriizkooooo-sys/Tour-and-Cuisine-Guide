import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, Response
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "trip_smart_2026_tri"
CORS(app)

# Lấy 11 key: GEMINI-KEY-0 đến GEMINI-KEY-10
API_KEYS = [os.environ.get(f"GEMINI-KEY-{i}") for i in range(11)]
API_KEYS = [k for k in API_KEYS if k]  # Loại bỏ None

# Tạo client cho từng key hợp lệ
clients = []
model_name = "gemini-1.5-flash"

for key in API_KEYS:
    try:
        client = genai.Client(api_key=key)
        clients.append(client)
    except:
        pass  # Bỏ qua key lỗi

DB_PATH = "chat_history.db"

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

def call_gemini(user_msg):
    if not clients:
        return {
            "text": "Xin lỗi bạn! Hiện tại chưa có API key Gemini nào khả dụng. "
                    "Mình sẽ sớm bổ sung để phục vụ tốt hơn nhé! 😊",
            "image_url": "",
            "youtube_link": "",
            "suggestions": ["Thử lại sau", "Cắm mốc trên bản đồ", "Tìm địa danh"]
        }

    prompt = (
        f"Bạn là hướng dẫn viên du lịch chuyên nghiệp về Việt Nam. "
        f"Người dùng hỏi: {user_msg}\n"
        "Trả về JSON thuần (không markdown, không giải thích): "
        "{\"text\": \"nội dung trả lời chi tiết, hấp dẫn\", "
        "\"image_url\": \"url ảnh đẹp về địa điểm (nếu có)\", "
        "\"youtube_link\": \"link YouTube gợi ý (nếu có)\", "
        "\"suggestions\": [\"gợi ý 1\", \"gợi ý 2\", \"gợi ý 3\"]}"
    )

    for client in clients:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.8,
                    top_p=0.9
                )
            )
            return json.loads(response.text)
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["quota", "resource_exhausted", "429", "invalid", "unauthorized"]):
                continue  # Thử key tiếp theo
            else:
                continue

    # Hết tất cả key
    return {
        "text": "Ôi không rồi! 😅 Hôm nay tất cả key Gemini miễn phí của mình đã hết lượt trả lời "
                "(Google chỉ cho ~20 lượt/key/ngày). "
                "Quota sẽ reset vào khoảng 15h chiều mai (giờ Việt Nam). "
                "Trong lúc chờ, bạn cứ thoải mái cắm mốc, tìm địa danh, khám phá bản đồ nhé! 🗺️❤️",
        "image_url": "",
        "youtube_link": "",
        "suggestions": ["Thử lại vào ngày mai", "Cắm mốc trên bản đồ", "Tìm địa danh khác"]
    }

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    msg = request.json.get("msg", "").strip()
    if not msg:
        return jsonify({"text": "Bạn chưa nhập gì cả! 😅"})

    ai_data = call_gemini(msg)

    # Lưu vào DB
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))

    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    if not sid:
        return jsonify([])

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()

    res = []
    for r in rows:
        try:
            content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
        except:
            content = r['content']
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    if not sid:
        return "Không có lịch sử", 400

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Font tiếng Việt
    font_path = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
    if os.path.exists(font_path):
        pdf.add_font('DejaVu', '', font_path, uni=True)
        pdf.set_font('DejaVu', '', 14)
    else:
        pdf.set_font('Arial', '', 14)

    pdf.cell(0, 15, txt="LỊCH TRÌNH DU LỊCH SMART TRAVEL 2026", ln=True, align='C')
    pdf.ln(10)

    for role, content, time_str in rows:
        prefix = "Bạn: " if role == "user" else "AI: "
        try:
            data = json.loads(content)
            text = data.get('text', '(Không có nội dung)')
        except:
            text = content

        pdf.set_font('DejaVu' if os.path.exists(font_path) else 'Arial', '', 12)
        pdf.multi_cell(0, 10, txt=f"[{time_str}] {prefix}{text}")
        pdf.ln(5)

    return Response(
        pdf.output(),
        mimetype='application/pdf',
        headers={"Content-Disposition": "attachment;filename=hanh-trinh-tri.pdf"}
    )

@app.route("/clear_history", methods=["POST"])
def clear():
    sid = request.cookies.get("session_id")
    if sid:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    resp = jsonify({"status": "ok"})
    resp.set_cookie("session_id", str(uuid.uuid4()), httponly=True)
    return resp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
