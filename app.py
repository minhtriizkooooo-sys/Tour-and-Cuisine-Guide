import os
import uuid
import sqlite3
import json
import sys
import traceback
import requests
from datetime import datetime
import pytz
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq, AuthenticationError, RateLimitError, APITimeoutError
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY_TCG") or os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# DEBUG khi khởi động
print(f"[STARTUP] {datetime.now(VN_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')} | "
      f"GROQ key: {'YES' if GROQ_API_KEY else 'NO'} | "
      f"SERPER key: {'YES' if SERPER_API_KEY else 'NO'}")

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (bao gồm tất cả quận, huyện, địa danh nổi bật như Bitexco, Landmark 81, Chợ Bến Thành, Phố đi bộ Nguyễn Huệ, Nhà thờ Đức Bà, Bưu điện Thành phố, các tòa nhà cao tầng, khu vui chơi, quán ăn...), Vũng Tàu và Bình Dương.

1. Nếu địa danh KHÔNG thuộc 3 nơi này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ du lịch TP.HCM, Vũng Tàu và Bình Dương. Nếu là địa điểm trong TP.HCM, thử mô tả rõ hơn nhé!"}

2. Nếu HỢP LỆ: Trả JSON với các trường bắt buộc:
{
  "is_valid": true,
  "text": "Nội dung chi tiết bằng tiếng Việt, dài ít nhất 1800 từ, phong phú, có chiều sâu, cấu trúc rõ ràng (dùng heading ##, ### nếu cần), bao gồm đầy đủ:
  - Lịch sử hình thành, phát triển qua các giai đoạn (thuộc địa, chiến tranh, đổi mới), sự kiện nổi bật, nhân vật lịch sử, ảnh hưởng đến hiện đại.
  - Văn hóa đặc trưng: lễ hội, phong tục, di sản, nghệ thuật dân gian, giá trị cốt lõi.
  - Con người địa phương: tính cách, lối sống, thói quen, tương tác với du khách, câu chuyện thực tế, sự khác biệt thế hệ.
  - Ẩm thực nổi bật: món đặc sản, nguồn gốc, nguyên liệu, cách chế biến chi tiết, địa chỉ quán ngon (tên + địa chỉ cụ thể + giá tham khảo), mẹo ăn, theo mùa.
  - Gợi ý du lịch chi tiết: check-in gần (khoảng cách, thời gian), hoạt động trải nghiệm, lộ trình 1-3 ngày (giờ cụ thể), lưu ý thời tiết/an toàn/chi phí/giờ mở cửa, mẹo tiết kiệm, hoạt động theo mùa, chỗ ít người biết.",
  "suggestions": ["3 câu hỏi gợi ý bằng tiếng Việt, liên quan sâu đến địa danh, mỗi câu là một string riêng biệt"]
}

Chỉ trả về JSON thuần túy, không có bất kỳ text nào ngoài JSON."""

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
    if not SERPER_API_KEY:
        return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": f"{query} Việt Nam thực tế du lịch"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        r = requests.post(url, headers=headers, data=payload, timeout=12)
        data = r.json()
        results = []
        for item in data.get("images", [])[:6]:
            url_img = item.get("imageUrl") or item.get("original")
            if url_img and url_img.startswith("http"):
                results.append({
                    "url": url_img,
                    "caption": item.get("title", query)[:100]
                })
        return results
    except Exception as e:
        print(f"[SERPER Images ERROR] {str(e)}")
        return []

def search_serper_youtube(query):
    if not SERPER_API_KEY:
        return []
    try:
        url = "https://google.serper.dev/videos"
        payload = json.dumps({"q": f"{query} du lịch trải nghiệm thực tế"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        r = requests.post(url, headers=headers, data=payload, timeout=12)
        data = r.json()
        results = []
        for item in data.get("videos", [])[:3]:
            link = item.get("link", "")
            if link and ("youtube.com/watch" in link or "youtu.be" in link):
                results.append(link)
        return results
    except Exception as e:
        print(f"[SERPER YouTube ERROR] {str(e)}")
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
        return jsonify({"text": "Bạn chưa nhập gì cả...", "images": [], "youtube_links": [], "suggestions": []})

    now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    print(f"[CHAT {now_vn}] REQUEST: '{msg[:80]}...' | Session: {sid[:8] if sid else 'NONE'}")

    if not GROQ_API_KEY:
        print("[ERROR] GROQ_API_KEY chưa được set")
        return jsonify({
            "text": "Lỗi hệ thống: Chưa cấu hình GROQ_API_KEY trên Render.",
            "images": [], "youtube_links": [], "suggestions": []
        })

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Model đang hoạt động năm 2026
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": msg}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4096,
            timeout=90
        )

        raw_response = completion.choices[0].message.content.strip()
        print(f"[GROQ OK] Length: {len(raw_response)} | Preview: {raw_response[:150]}...")

        ai_res = json.loads(raw_response)

        if not ai_res.get("is_valid", False):
            return jsonify({
                "text": ai_res.get("text", "Không hợp lệ."),
                "images": [], "youtube_links": [], "suggestions": []
            })

        # Lưu tin nhắn vào DB (cải thiện để xuất PDF sau này)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (sid, "user", msg, now_vn)
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (sid, "bot", json.dumps(ai_res), now_vn)
            )
            conn.commit()

        place_name = msg.strip()
        images = search_serper_images(place_name)
        youtube_links = search_serper_youtube(place_name)

        return jsonify({
            "text": ai_res.get("text", "Không có nội dung trả về."),
            "images": images,
            "youtube_links": youtube_links,
            "suggestions": ai_res.get("suggestions", [])
        })

    except json.JSONDecodeError:
        return jsonify({"text": "Lỗi: AI trả về định dạng không đúng.", "images": [], "youtube_links": [], "suggestions": []})
    except AuthenticationError:
        return jsonify({"text": "Lỗi: GROQ API key không hợp lệ (401). Kiểm tra lại key.", "images": [], "youtube_links": [], "suggestions": []})
    except RateLimitError:
        return jsonify({"text": "Hết quota Groq (429). Đợi reset hoặc nâng cấp plan.", "images": [], "youtube_links": [], "suggestions": []})
    except APITimeoutError:
        return jsonify({"text": "Groq timeout. Thử lại sau vài phút.", "images": [], "youtube_links": [], "suggestions": []})
    except Exception as e:
        print(f"[CRITICAL] {type(e).__name__}: {str(e)}")
        traceback.print_exc(file=sys.stdout)
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "images": [], "youtube_links": [], "suggestions": []})

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    if not sid:
        return jsonify({"error": "Không tìm thấy session"}), 400

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        messages = cur.fetchall()

    if not messages:
        return jsonify({"error": "Chưa có lịch sử chat"}), 404

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "LỊCH SỬ TRÒ CHUYỆN - VIET NAM TRAVEL AI GUIDE 2026", ln=1, align="C")
    pdf.ln(10)

    for role, content, created_at in messages:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, f"{role.upper()} - {created_at}", ln=1)
        pdf.set_font("Arial", size=11)

        try:
            data = json.loads(content) if role == "bot" else {"text": content}
            text = data.get("text", content)
        except:
            text = content

        pdf.multi_cell(0, 6, text.strip())
        pdf.ln(5)

    pdf_file = f"chat_history_{sid[:8]}.pdf"
    pdf.output(pdf_file)

    return send_file(pdf_file, as_attachment=True, download_name="lich-su-tro-chuyen.pdf")

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    if not sid:
        return jsonify([])

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 50", (sid,))
        rows = cur.fetchall()

    history = []
    for role, content in rows:
        try:
            parsed = json.loads(content) if role == "bot" else content
        except:
            parsed = content
        history.append({"role": role, "content": parsed})

    return jsonify(history)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    if sid:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
            conn.commit()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
