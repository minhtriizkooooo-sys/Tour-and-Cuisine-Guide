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

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (Thành phố Hồ Chí Minh), bao gồm tất cả các quận, huyện, thành phố trực thuộc cũ và mới (sau mọi đợt sáp nhập, chia tách đến năm 2026), tất cả phường, xã, thị trấn, tất cả tên đường, tên khu dân cư, tên tòa nhà, chung cư, trung tâm thương mại, trường học, bệnh viện, cơ quan nhà nước, công ty tư nhân, chùa, đình, miếu, chợ, bến xe, ga, cảng, khu công nghiệp... có liên quan đến địa bàn TP.HCM (Sài Gòn).

QUY TẮC BẮT BUỘC:
1. BẤT KỲ địa danh, địa điểm, tòa nhà, khu vực nào KHÔNG rõ ràng thuộc TP.HCM → Trả NGAY lập tức JSON:
{"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ thông tin du lịch tại TP.HCM thôi nhé!"}

2. Nếu có khả năng liên quan đến TP.HCM (kể cả tên không dấu, tên cũ, tên viết tắt, tên thương mại, tên phường/xã/huyện sau sáp nhập): coi là HỢP LỆ → Trả về JSON đầy đủ.

3. Nội dung BẮT BUỘC phải phong phú, chi tiết (>2200 từ), dùng markdown ##, ###, ####, danh sách, *in nghiêng*, **đậm** khi phù hợp. Phải có đủ các phần sau theo đúng thứ tự:
- ## Lịch sử hình thành và phát triển (từ quá khứ → hiện tại → dự báo đến năm 2026-2030)
- ## Con người, văn hóa, lối sống đặc trưng của cư dân địa phương
- ## Ẩm thực nổi bật (liệt kê 8-12 món đặc trưng + địa chỉ cụ thể + mức giá tham khảo năm 2026)
- ## Gợi ý lịch trình du lịch chi tiết (có 3 lựa chọn: 1 ngày, 2 ngày, 3 ngày – kèm thời gian, phương tiện, chi phí ước tính)
- ## Dự báo & tầm nhìn tương lai phát triển TP.HCM đến 2026-2030 (hạ tầng, đô thị, du lịch, công nghệ, thay đổi cảnh quan…)

4. Cuối cùng BẮT BUỘC thêm mảng "suggestions": chứa 3-5 câu hỏi tiếp theo, **phải chắc chắn 100% liên quan đến TP.HCM**.

5. Trả về **chỉ JSON thuần túy**, định dạng chính xác.
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
        full_q = f"{query} TP.HCM du lịch thực tế 2025 2026 view đẹp"
        payload = json.dumps({"q": full_q})
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
        full_q = f"{query} TP.HCM du lịch trải nghiệm 2025 2026 tiếng Việt"
        payload = json.dumps({"q": full_q})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        return [i.get("link") for i in resp.json().get("videos", []) if "youtube" in i.get("link", "").lower()][:4]
    except:
        return []

def search_serper_future_images():
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": "TP.HCM phát triển đô thị tương lai 2026 2027 2030 hình ảnh dự án thực tế"})
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
        payload = json.dumps({"q": "tương lai TP.HCM 2026 2030 phát triển đô thị hạ tầng video tiếng Việt"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        return [i.get("link") for i in resp.json().get("videos", []) if "youtube" in i.get("link", "").lower()][:3]
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
            search_term = clean_query or msg
            ai_res["images"] = search_serper_images(search_term)
            ai_res["youtube_links"] = search_serper_youtube(search_term)
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
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "is_valid": False})

# Các route khác giữ nguyên (history, clear_history, export_pdf)

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()
    formatted_history = []
    for r, c in rows:
        try:
            content = json.loads(c) if r == "bot" else c
        except:
            content = c
        formatted_history.append({"role": r, "content": content})
    return jsonify(formatted_history)

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
    if not rows:
        return "Không có dữ liệu để xuất."
    pdf = FPDF()
    pdf.add_page()
    font_path = os.path.join("static", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=11)
    else:
        pdf.set_font("Arial", size=11)
    now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    pdf.cell(200, 10, txt="LỊCH TRÌNH & THÔNG TIN DU LỊCH TP.HCM 2026", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Xuất lúc: {now_vn} (Giờ Việt Nam)", ln=True, align='C')
    pdf.ln(12)
    for role, content in rows:
        label = "BẠN: " if role == "user" else "AI: "
        if role == "bot":
            try:
                data = json.loads(content)
                text = data.get("text", "")
                pdf.multi_cell(0, 8, txt=f"{label}\n{text}\n")
            except:
                pdf.multi_cell(0, 8, txt=f"{label}{content}\n")
        else:
            pdf.multi_cell(0, 8, txt=f"{label}{content}\n")
        pdf.ln(6)
    path = f"history_{sid[:12]}.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
