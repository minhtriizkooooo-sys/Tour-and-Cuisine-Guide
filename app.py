import os
import uuid
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
CORS(app)

# ------------------- TỰ ĐỘNG LẤY TẤT CẢ KEY CÓ TÊN GEMINI-KEY-... -------------------
# Ví dụ: GEMINI-KEY-0, GEMINI-KEY-1, ..., GEMINI-KEY-10
API_KEYS = []
for key_name, value in os.environ.items():
    if key_name.startswith("GEMINI-KEY-") and value:
        API_KEYS.append(value.strip())

# Tạo client cho từng key hợp lệ
clients = []
model_name = "gemini-1.5-flash"  # Model nhanh, rẻ, phù hợp nhất cho app du lịch

for key in API_KEYS:
    try:
        client = genai.Client(api_key=key)
        clients.append(client)
    except Exception as e:
        print(f"Key không hợp lệ (bị bỏ qua): {e}")  # Log để debug trên Render

DB_PATH = "chat_history.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT, role TEXT, content TEXT, created_at TEXT
            )
        """)
init_db()

def call_gemini(user_msg):
    if not clients:
        return {
            "history": "Xin lỗi bạn, hiện tại hệ thống chưa có API key Gemini nào khả dụng. "
                       "Mình sẽ sớm bổ sung thêm để phục vụ tốt hơn! 😊",
            "culture": "", "cuisine": "", "travel_tips": "", "youtube_keyword": "",
            "suggestions": ["Thử lại sau", "Khám phá bản đồ", "Vẽ lộ trình du lịch"]
        }

    prompt = (
        f"Bạn là hướng dẫn viên du lịch chuyên nghiệp, nhiệt tình và am hiểu sâu về Việt Nam. "
        f"Hãy kể chi tiết về địa điểm: {user_msg}. "
        "Trả về JSON thuần túy (không markdown, không giải thích): "
        "{\"history\": \"...\", \"culture\": \"...\", \"cuisine\": \"...\", "
        "\"travel_tips\": \"...\", \"image_query\": \"...\", \"youtube_keyword\": \"...\", "
        "\"suggestions\": [\"câu hỏi 1\", \"câu hỏi 2\", \"câu hỏi 3\"]}"
    )

    # Thử từng client (tức từng key) một
    for client in clients:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                    top_p=0.9
                )
            )
            return json.loads(response.text)
        except Exception as e:
            err_str = str(e).lower()
            # Nếu lỗi do quota hết, key invalid, rate limit → bỏ qua và thử key tiếp
            if any(keyword in err_str for keyword in ["quota", "resource_exhausted", "429", "invalid", "unauthorized", "billing"]):
                continue
            else:
                # Lỗi mạng hoặc server Google → vẫn thử key khác
                continue

    # Nếu hết sạch tất cả key
    return {
        "history": "Ôi không! 😅 Hôm nay tất cả các API key miễn phí của mình đã hết lượt trả lời rồi "
                   "(Google chỉ cho khoảng 20 lượt/key/ngày). "
                   "Mình đang cố gắng thêm key mới để phục vụ mọi người lâu hơn! ❤️",
        "culture": "Trong lúc chờ, bạn có thể thoải mái dùng bản đồ, tìm địa điểm, vẽ lộ trình nhé – những tính năng này không cần AI vẫn hoạt động mượt mà!",
        "cuisine": "",
        "travel_tips": "Mẹo nhỏ: Quota sẽ reset vào khoảng trưa ngày mai (giờ Việt Nam). Bạn quay lại thử nhé! 🌅",
        "youtube_keyword": "",
        "suggestions": ["Thử lại vào ngày mai", "Tìm địa điểm trên bản đồ", "Vẽ lộ trình du lịch", "Hỏi về Đà Lạt"]
    }

# ====================== CÁC ROUTE GIỮ NGUYÊN HOÀN TOÀN ======================

@app.route("/")
def index():
    sid = str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    msg = request.json.get("msg", "").strip()
    ai_data = call_gemini(msg)
   
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
        content = r['content']
        if r['role'] == 'bot':
            try:
                content = json.loads(content)
            except:
                pass
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    if not sid:
        return "Không có phiên chat", 400
   
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id",
            (sid,)
        ).fetchall()
   
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)
   
    font_dir = app.static_folder
    regular_path = os.path.join(font_dir, "DejaVuSans.ttf")
    bold_path = os.path.join(font_dir, "DejaVuSans-Bold.ttf")
   
    if os.path.exists(regular_path):
        pdf.add_font("DejaVu", "", regular_path, uni=True)
    if os.path.exists(bold_path):
        pdf.add_font("DejaVu", "B", bold_path, uni=True)
   
    pdf.set_font("DejaVu", size=16)
    pdf.cell(0, 15, txt="LỊCH SỬ DU LỊCH - SMART TRAVEL AI", ln=True, align='C')
    pdf.ln(10)
   
    for role, content, created_at in rows:
        label = "BẠN: " if role == "user" else "AI: "
        time_str = created_at
       
        pdf.set_font("DejaVu", "B" if os.path.exists(bold_path) else "", 12)
        pdf.multi_cell(0, 10, f"[{time_str}] {label}")
        pdf.ln(5)
       
        pdf.set_font("DejaVu", size=11)
       
        if role == "bot":
            try:
                data = json.loads(content)
                sections = [
                    f"Lịch sử: {data.get('history', '')}",
                    f"Văn hóa: {data.get('culture', '')}",
                    f"Ẩm thực: {data.get('cuisine', '')}",
                    f"Mẹo du lịch: {data.get('travel_tips', '')}",
                    f"YouTube tìm kiếm: {data.get('youtube_keyword', '')}",
                    "Gợi ý địa điểm tiếp theo:",
                ]
                for section in sections:
                    if ':' in section:
                        value = section.split(':', 1)[1].strip()
                        if value:
                            pdf.multi_cell(0, 9, section)
                            pdf.ln(3)
               
                suggestions = data.get('suggestions', [])
                if suggestions:
                    pdf.multi_cell(0, 9, "- " + "\n- ".join(suggestions))
                    pdf.ln(5)
            except:
                pdf.multi_cell(0, 9, content[:1500])
        else:
            pdf.multi_cell(0, 9, content)
       
        pdf.ln(12)
   
    pdf_path = "/tmp/history.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, as_attachment=True, download_name="lich_su_du_lich.pdf")

@app.route("/clear_history", methods=["POST"])
def clear():
    sid = request.cookies.get("session_id")
    if sid:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    resp = jsonify({"status": "deleted"})
    resp.set_cookie("session_id", str(uuid.uuid4()), httponly=True)
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
