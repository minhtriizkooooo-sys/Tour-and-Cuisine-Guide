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

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch hàng đầu, người Sài Gòn chính gốc, cực kỳ đam mê và am hiểu sâu sắc về TP.HCM. Bạn kể chuyện du lịch một cách **hấp dẫn, sống động, giàu cảm xúc**, như đang dẫn tour trực tiếp cho bạn bè thân thiết. Ngôn ngữ phải **thân thiện, gần gũi, nhiệt huyết**, xen kẽ miêu tả cảnh quan, mùi vị, âm thanh, cảm giác, câu chuyện lịch sử thú vị, bí mật địa phương, và dự báo tương lai đầy hứng khởi.

Bạn CHỈ hỗ trợ thông tin du lịch **TP.HCM** (bao gồm mọi quận/huyện, tòa nhà biểu tượng, landmark, trung tâm thương mại, khu đô thị, phố đi bộ... ví dụ: Landmark 81, Bitexco Financial Tower, Saigon Marina, IFC One Saigon, Crescent Mall, phố đi bộ Nguyễn Huệ, chợ Bến Thành, Bùi Viện, Thủ Thiêm, Củ Chi...).

Nếu địa danh/tòa nhà/khu vực KHÔNG thuộc TP.HCM → Trả ngay JSON:
{
  "is_valid": false,
  "text": "Xin lỗi bạn nhé, mình chỉ am hiểu và hỗ trợ du lịch tại Sài Gòn – TP.HCM thôi! Nếu bạn hỏi về nơi khác, mình chưa rành lắm đâu. Hỏi mình về Landmark 81, phố đi bộ hay món ăn Sài Gòn đi nào! 😄"
}

Nếu HỢP LỆ: Trả về JSON **chi tiết cực kỳ phong phú** (tối thiểu 2500–3500 từ), viết bằng tiếng Việt **hay, cuốn hút, chuyên nghiệp** như bài viết báo du lịch cao cấp. Sử dụng markdown đẹp mắt:

- **Ngôn ngữ**: Sống động, giàu hình ảnh, kể chuyện, thêm câu hỏi tu từ, cảm thán, miêu tả giác quan (mùi, vị, âm thanh, cảm xúc).
- **Cấu trúc bắt buộc** (đúng thứ tự, mỗi phần dài, sâu):
  ## 1. Lịch sử hình thành và phát triển
     Kể chuyện từ quá khứ (nguồn gốc, sự kiện lịch sử quan trọng), hiện tại (thay đổi lớn), đến dự báo 2026–2030 (dự án cụ thể, thay đổi cảnh quan, cơ hội du lịch).
  ## 2. Con người, văn hóa và lối sống đặc trưng
     Miêu tả tính cách người dân địa phương, phong tục, lễ hội, câu chuyện đời thường, sự giao thoa Đông-Tây, cảm nhận khi sống/làm việc ở đây.
  ## 3. Ẩm thực nổi bật
     Liệt kê 10–15 món đặc trưng nhất, mô tả hương vị chi tiết, địa chỉ cụ thể (quán nổi tiếng + địa chỉ đường phố/quận), giá tham khảo năm 2026, gợi ý cách ăn, mẹo tránh đông.
     Dùng danh sách đánh số hoặc bullet + **bold** tên món.
  ## 4. Gợi ý lịch trình du lịch chi tiết
     Đưa ra 3 lựa chọn rõ ràng:
     - **Lịch trình 1 ngày** (ngắn gọn, tập trung highlight)
     - **Lịch trình 2 ngày** (cân bằng, khám phá sâu hơn)
     - **Lịch trình 3 ngày** (toàn diện, có thời gian nghỉ ngơi)
     Mỗi lịch trình ghi rõ: thời gian, địa điểm, phương tiện di chuyển, chi phí ước tính (ăn uống + vé + di chuyển), mẹo hay.
  ## 5. Tầm nhìn tương lai & dự án phát triển đến 2026–2030
     Dự báo hấp dẫn: hạ tầng mới (metro, cầu Thủ Thiêm, khu đô thị thông minh), thay đổi cảnh quan, cơ hội du lịch mới, cảm hứng cho du khách tương lai.

Cuối cùng thêm mảng gợi ý 3–5 câu hỏi hay, kích thích người dùng hỏi tiếp:
"suggestions": ["Bạn muốn khám phá ẩm thực đường phố quanh đây không?", "Lịch trình 2 ngày cho gia đình có trẻ nhỏ thì sao?", ...]

Trả về **CHỈ JSON thuần túy**, không thêm bất kỳ text, comment hay lời giải thích nào ngoài JSON.
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
        payload = json.dumps({"q": f"{query} TP.HCM du lịch thực tế 2025 2026"})
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
        search_q = f"{query} du lịch trải nghiệm tiếng Việt review tại chỗ 2025 2026 -english -sub -subtitle"
        payload = json.dumps({"q": search_q})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=12)
        videos = resp.json().get("videos", [])
        filtered = []
        for v in videos:
            link = v.get("link", "")
            if "youtube" not in link.lower():
                continue
            title = (v.get("title") or "").lower()
            snippet = (v.get("snippet") or "").lower()
            if any(kw in title or kw in snippet for kw in ["tiếng việt", "review", "trải nghiệm", "thực tế", "du lịch", query.lower()]):
                filtered.append(link)
        return filtered[:3]
    except:
        return []

def search_serper_future_images():
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": "TP.HCM phát triển tương lai 2026 2027 2030 hình ảnh dự án thực tế đô thị cao tầng metro thủ thiêm"})
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
        payload = json.dumps({"q": "TP.HCM tương lai 2026 2027 2030 phát triển đô thị hạ tầng dự án metro Thủ Thiêm video tiếng Việt review thực tế"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=12)
        videos = resp.json().get("videos", [])
        filtered = []
        for v in videos:
            link = v.get("link", "")
            if "youtube" not in link.lower(): continue
            title = (v.get("title") or "").lower()
            snippet = (v.get("snippet") or "").lower()
            if any(kw in title or kw in snippet for kw in ["tiếng việt", "dự án", "phát triển", "tương lai", "2026", "metro", "thủ thiêm"]):
                filtered.append(link)
        return filtered[:2]
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
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4096
        )
        ai_res = json.loads(completion.choices[0].message.content)

        if ai_res.get("is_valid", False):
            clean_query = msg.replace("Thông tin du lịch chi tiết về", "").replace("tại TP.HCM năm 2026", "").strip()
            try:
                ai_res["images"] = search_serper_images(clean_query or msg)
                ai_res["youtube_links"] = search_serper_youtube(clean_query or msg)
                ai_res["future_images"] = search_serper_future_images()
                ai_res["future_youtube_links"] = search_serper_future_youtube()
            except Exception as search_err:
                print("Search error:", search_err)
                ai_res["images"] = ai_res["youtube_links"] = ai_res["future_images"] = ai_res["future_youtube_links"] = []

        now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, now_vn))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_res), now_vn))
        return jsonify(ai_res)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "is_valid": False})

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()
    formatted = []
    for r, c in rows:
        content = json.loads(c) if r == "bot" else c
        formatted.append({"role": r, "content": content})
    return jsonify(formatted)

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
    if not rows: return "Không có dữ liệu."
    pdf = FPDF()
    pdf.add_page()
    font_path = os.path.join("static", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=11)
    else:
        pdf.set_font("Arial", size=11)
    now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    pdf.cell(200, 10, txt="THÔNG TIN DU LỊCH TP.HCM 2026", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Xuất lúc: {now_vn}", ln=True, align='C')
    pdf.ln(10)
    for role, content in rows:
        label = "BẠN: " if role == "user" else "AI: "
        if role == "bot":
            try:
                data = json.loads(content)
                text = data.get("text", "")
                pdf.multi_cell(0, 8, txt=f"{label}\n{text}")
            except:
                pdf.multi_cell(0, 8, txt=f"{label}{content}")
        else:
            pdf.multi_cell(0, 8, txt=f"{label}{content}")
        pdf.ln(6)
    path = f"history_{sid[:12]}.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
