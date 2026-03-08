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
import pytz

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

# Lấy API keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"

# Debug ngay lúc khởi động
print(f"[STARTUP] GROQ_API_KEY prefix: {GROQ_API_KEY[:6] if GROQ_API_KEY else 'NOT SET'}...")
print(f"[STARTUP] SERPER_API_KEY prefix: {SERPER_API_KEY[:6] if SERPER_API_KEY else 'NOT SET'}...")

VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (bao gồm tất cả quận, huyện, địa danh nổi bật như Bitexco, Landmark 81, Chợ Bến Thành, Phố đi bộ Nguyễn Huệ, Nhà thờ Đức Bà, Bưu điện Thành phố, các tòa nhà cao tầng, khu vui chơi, quán ăn...), Vũng Tàu và Bình Dương.
1. Nếu địa danh KHÔNG thuộc 3 nơi này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ du lịch TP.HCM, Vũng Tàu và Bình Dương. Nếu là địa điểm trong TP.HCM, thử mô tả rõ hơn nhé!"}
2. Nếu HỢP LỆ: Trả JSON {"is_valid": true, "text": "Nội dung chi tiết bằng tiếng Việt, dài >1800 từ, phong phú thông tin, có chiều sâu, cấu trúc rõ ràng và liên quan trực tiếp đến địa danh hỏi:
- Lịch sử hình thành, phát triển qua các giai đoạn quan trọng (thời kỳ thuộc địa, chiến tranh, đổi mới), sự kiện nổi bật, nhân vật lịch sử liên quan, ảnh hưởng đến hiện đại.
- Văn hóa đặc trưng: lễ hội truyền thống, phong tục tập quán, di sản văn hóa UNESCO hoặc địa phương, nghệ thuật dân gian, lễ hội hiện đại, giá trị văn hóa cốt lõi.
- Con người địa phương: tính cách thân thiện, lối sống năng động, thói quen sinh hoạt hàng ngày, cách tương tác với du khách, câu chuyện thực tế từ người dân, sự khác biệt giữa các thế hệ.
- Ẩm thực nổi bật: món ăn đặc sản, nguồn gốc lịch sử, nguyên liệu địa phương, cách chế biến chi tiết, địa chỉ quán ăn ngon gần đó (tên quán, địa chỉ cụ thể, giá tham khảo), mẹo thưởng thức, món ăn theo mùa.
- Gợi ý du lịch chi tiết: địa điểm check-in gần (khoảng cách, thời gian di chuyển), hoạt động trải nghiệm (ăn chơi, nghỉ dưỡng, khám phá văn hóa), lộ trình mẫu 1-3 ngày với thời gian cụ thể, lưu ý thời tiết, an toàn, chi phí tham khảo, giờ mở cửa, mẹo du lịch tiết kiệm, hoạt động đặc biệt theo mùa, các địa điểm ít người biết.
Viết hấp dẫn, sinh động, gần gũi, dựa trên kiến thức thực tế, dùng ví dụ minh họa, câu chuyện kể, khuyến khích du khách trải nghiệm sâu sắc.", "suggestions": ["3 câu hỏi gợi ý liên quan sâu đến địa danh vừa hỏi, bằng tiếng Việt"]}
Chỉ trả JSON thuần, không thêm text ngoài."""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")

init_db()

def search_serper(query, search_type="images"):
    if not SERPER_API_KEY:
        print("[DEBUG] SERPER_API_KEY not set, returning empty")
        return []
    
    base_q = f"{query} du lịch Việt Nam thực tế review chi tiết địa danh"
    q = f"{query} du lịch review youtube trải nghiệm địa danh" if search_type == "videos" else base_q + " hình ảnh đẹp check-in thực tế địa danh"
    
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
            videos = [i.get('link', '') for i in res.get('videos', [])[:10] if 'youtube' in i.get('link', '').lower()]
            print(f"[DEBUG Videos] Query: {q} → Found {len(videos)} videos")
            return videos
    except Exception as e:
        print(f"[Serper error {search_type}]: {e}")
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

    if not GROQ_API_KEY:
        print("[ERROR] GROQ_API_KEY is not set in environment variables!")
        return jsonify({"text": "Lỗi hệ thống: API key Groq chưa được cấu hình trên server.", "images": [], "youtube_links": []})

    client = Groq(api_key=GROQ_API_KEY)

    try:
        print(f"[DEBUG] Gửi yêu cầu Groq: msg='{msg[:80]}...' | model=llama-3.1-8b-instant | tokens max=2048")
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",          # ← Model nhẹ để test nhanh, đổi lại 70b khi ổn
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=2048,                       # ← Giảm để tiết kiệm quota khi test
        )

        raw_response = completion.choices[0].message.content
        print(f"[DEBUG] Groq raw response (first 300 chars): {raw_response[:300]}...")

        ai_res = json.loads(raw_response)

        images = search_serper(msg, "images") if ai_res.get("is_valid", False) else []
        videos = search_serper(msg, "videos") if ai_res.get("is_valid", False) else []

        data = {
            "text": ai_res.get("text", "Không có nội dung."),
            "images": images,
            "youtube_links": videos,
            "suggestions": ai_res.get("suggestions", ["Du lịch Landmark 81", "Review Vũng Tàu", "Bình Dương có gì chơi"])
        }

        now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, now_vn))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(data, ensure_ascii=False), now_vn))

        print("[DEBUG] Chat response sent successfully")
        return jsonify(data)

    except Exception as e:
        error_str = f"Groq error: {type(e).__name__} - {str(e)}"
        print(error_str)
        if 'completion' in locals():
            print(f"[DEBUG] Raw Groq content (if available): {completion.choices[0].message.content[:500]}...")
        return jsonify({"text": f"Lỗi khi gọi Groq: {error_str}", "images": [], "youtube_links": []})

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
