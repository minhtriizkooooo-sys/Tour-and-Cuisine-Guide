import os, uuid, sqlite3, json, time, random
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
CORS(app)

# --- CẤU HÌNH API KEYS ---
# Lấy danh sách Key từ Environment của Render
API_KEYS = [v.strip() for k, v in os.environ.items() if k.startswith("GEMINI-KEY-") and v]

clients = []
for key in API_KEYS:
    try:
        clients.append(genai.Client(api_key=key))
    except Exception as e:
        print(f"Bỏ qua key lỗi lúc khởi tạo: {e}")

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
        return {"history": "Hệ thống chưa có API Key. Bạn hãy kiểm tra Environment Variables."}

    prompt = (
        f"Bạn là hướng dẫn viên du lịch VN. Review địa danh hoặc lộ trình: {user_msg}. "
        "Trả về JSON: {\"history\": \"...\", \"culture\": \"...\", \"cuisine\": \"...\", "
        "\"travel_tips\": \"...\", \"youtube_keyword\": \"...\", \"suggestions\": [\"...\", \"...\"]}"
    )

    # Trộn ngẫu nhiên danh sách Key để tránh bị giới hạn (Rate Limit)
    pool = list(clients)
    random.shuffle(pool)

    for client in pool:
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", 
                    temperature=0.7
                )
            )
            return json.loads(response.text)
        except Exception as e:
            # Ghi log lỗi ra server để Trí theo dõi, không gửi mã lỗi 404 về cho người dùng
            print(f"Lỗi Key đang thử: {str(e)}")
            if "429" in str(e):
                time.sleep(1)
            continue # Thử chìa khóa tiếp theo

    return {
        "history": "Hiện tại AI đang bận xử lý nhiều yêu cầu. Bạn vui lòng đợi vài giây rồi thử lại nhé! 🌿",
        "suggestions": ["Thử lại", "Tìm địa điểm khác"]
    }

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    ai_data = call_gemini(msg)
    
    with sqlite3.connect(DB_PATH) as conn:
        # Lưu tin nhắn của người dùng
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "user", msg, datetime.now().strftime("%H:%M")))
        # Lưu phản hồi của AI (dưới dạng chuỗi JSON)
        conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                     (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    
    result = []
    for r in rows:
        try:
            # Nếu là tin của bot thì giải mã JSON để hiển thị
            content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
        except:
            content = r['content']
        result.append({"role": r['role'], "content": content})
    return jsonify(result)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "LICH SU DU LICH - SMART TRAVEL AI", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=10)
    for role, content, timestamp in rows:
        if role == "bot":
            try:
                data = json.loads(content)
                text = f"[{timestamp}] AI: {data.get('history', '')[:200]}..."
            except:
                text = f"[{timestamp}] AI: {content[:200]}"
        else:
            text = f"[{timestamp}] BAN: {content}"
        
        # Xử lý để PDF không bị lỗi ký tự lạ khi chưa có font tiếng Việt
        pdf.multi_cell(0, 10, text.encode('latin-1', 'ignore').decode('latin-1'))
        pdf.ln(2)
    
    path = "/tmp/history.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    # Render yêu cầu dùng port từ environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
