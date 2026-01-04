import os
import uuid
import sqlite3
import json
import time
import random
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, make_response, Response
from flask_cors import CORS
from google import genai
from google.genai import types
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "trip_smart_2026_final_fix" 
CORS(app)

# --- CẤU HÌNH API KEYS ---
API_KEYS = []
for key, value in os.environ.items():
    if "API_KEY" in key.upper() and value:
        # Tách key nếu người dùng nhập chuỗi phân cách bằng dấu phẩy
        parts = [k.strip() for k in value.split(',') if k.strip().startswith("AIza")]
        API_KEYS.extend(parts)

API_KEYS = list(set(API_KEYS))
print(f"[SYSTEM] Đã kích hoạt {len(API_KEYS)} API Keys.")

# Sử dụng model 1.5-flash-8b để có giới hạn RPM (Requests Per Minute) cao nhất
model_name = "gemini-1.5-flash-8b" 
DB_PATH = "chat_history.db"

system_instruction = """
Bạn là AI Hướng dẫn Du lịch Việt Nam. Trả về JSON thuần (không markdown code block):
{
  "text": "Nội dung (Lịch sử, Văn hóa, Ẩm thực, Lịch trình).",
  "images": [{"url": "https://images.unsplash.com/featured/?{place},vietnam", "caption": "Mô tả"}],
  "youtube_links": ["Link video"],
  "suggestions": ["Gợi ý 1"]
}
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")
init_db()

def get_youtube_id(url):
    if not url: return None
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else None

def get_ai_response(session_id, user_msg):
    if not API_KEYS:
        return {"text": "Chưa có API Key.", "images": [], "youtube_links": []}

    # Rút gọn lịch sử tối đa (chỉ lấy 4 câu) để tránh lỗi quota do token
    history_contents = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 4", (session_id,)).fetchall()
            for r in reversed(rows):
                role = "user" if r['role'] == 'user' else "model"
                txt = r['content']
                if role == "model":
                    try: txt = json.loads(txt).get('text', '...')
                    except: pass
                history_contents.append(types.Content(role=role, parts=[types.Part(text=txt)]))
    except: pass

    contents = history_contents + [types.Content(role="user", parts=[types.Part(text=user_msg)])]

    # Xáo trộn danh sách để không tập trung vào 1 key đầu tiên
    shuffled_keys = random.sample(API_KEYS, len(API_KEYS))

    for i, key in enumerate(shuffled_keys):
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction, 
                    response_mime_type="application/json",
                    temperature=0.4 # Giảm nhiệt độ để AI bớt "sáng tạo" gây lỗi JSON
                )
            )
            
            if response and response.text:
                ai_data = json.loads(response.text)
                if 'youtube_links' in ai_data:
                    ai_data['youtube_links'] = [l for l in ai_data['youtube_links'] if get_youtube_id(l)]
                return ai_data
                
        except Exception as e:
            err = str(e)
            print(f"[DEBUG] Key {i+1} lỗi: {err[:50]}...")
            # Nếu lỗi quota, nghỉ 1.5 giây để server Google bớt chặn IP Render
            if "429" in err or "quota" in err.lower():
                time.sleep(1.5)
            continue

    return {
        "text": "⚠️ Toàn bộ 11 cổng kết nối đều đang quá tải. Vui lòng quay lại sau 30-60 giây.",
        "images": [], "youtube_links": [], "suggestions": ["Thử lại sau ít phút"]
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
    if not msg: return jsonify({"text": "..."})
    
    ai_data = get_ai_response(sid, msg) 
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, datetime.now().strftime("%H:%M")))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_data, ensure_ascii=False), datetime.now().strftime("%H:%M")))
    except: pass
    return jsonify(ai_data)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    res = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
    for r in rows:
        try: content = json.loads(r['content']) if r['role'] == 'bot' else r['content']
        except: content = r['content']
        res.append({"role": r['role'], "content": content})
    return jsonify(res)

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    if not sid: return "Không có lịch sử", 400
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
        pdf = FPDF()
        pdf.add_page()
        fpath = os.path.join(app.root_path, 'static', 'DejaVuSans.ttf')
        if os.path.exists(fpath):
            pdf.add_font('DejaVu', '', fpath)
            pdf.set_font('DejaVu', '', 11)
        else: pdf.set_font('Arial', '', 11)

        for role, content, time_str in rows:
            prefix = "User: " if role == "user" else "AI: "
            try: text = json.loads(content).get('text', '')
            except: text = content
            text = text.replace("**", "").replace("__", "")
            pdf.multi_cell(0, 8, txt=f"[{time_str}] {prefix}{text}")
            pdf.ln(2)
        return Response(bytes(pdf.output()), mimetype='application/pdf', headers={"Content-Disposition": "attachment;filename=travel.pdf"})
    except Exception as e: return str(e), 500

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    if sid:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    resp = jsonify({"status": "ok"})
    resp.set_cookie("session_id", str(uuid.uuid4()), httponly=True) 
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
