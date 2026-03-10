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
import tempfile
import os as os_module  # để unlink file

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY_TCG") or os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

print(f"[STARTUP {datetime.now(VN_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}] "
      f"GROQ key exists: {bool(GROQ_API_KEY)} | SERPER key exists: {bool(SERPER_API_KEY)}")

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (bao gồm tất cả quận, huyện, địa danh nổi bật như Bitexco, Landmark 81, Chợ Bến Thành, Phố đi bộ Nguyễn Huệ, Nhà thờ Đức Bà, Bưu điện Thành phố, các tòa nhà cao tầng, khu vui chơi, quán ăn...), Vũng Tàu và Bình Dương.

1. Nếu địa danh KHÔNG thuộc 3 nơi này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ du lịch TP.HCM, Vũng Tàu và Bình Dương. Nếu là địa điểm trong TP.HCM, thử mô tả rõ hơn nhé!"}

2. Nếu HỢP LỆ: Trả JSON với các trường bắt buộc:
{
  "is_valid": true,
  "text": "Nội dung chi tiết bằng tiếng Việt, dài ít nhất 1800 từ, phong phú, có chiều sâu, cấu trúc rõ ràng...",
  "suggestions": ["3 câu hỏi gợi ý bằng tiếng Việt, liên quan sâu đến địa danh"]
}

Chỉ trả về JSON thuần túy, không thêm text ngoài JSON."""

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
        print("[SERPER] API key missing → no images")
        return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": f"{query} Việt Nam thực tế du lịch 2025 2026"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        results = []
        for item in data.get("images", [])[:6]:
            img_url = item.get("imageUrl") or item.get("original") or item.get("thumbnail")
            if img_url and img_url.startswith("http"):
                results.append({
                    "url": img_url,
                    "caption": item.get("title", query)[:120] or "Ảnh thực tế"
                })
        print(f"[SERPER Images] Found {len(results)} images for '{query}'")
        return results
    except Exception as e:
        print(f"[SERPER Images ERROR] {str(e)}")
        return []

def search_serper_youtube(query):
    if not SERPER_API_KEY:
        return []
    try:
        url = "https://google.serper.dev/videos"
        payload = json.dumps({"q": f"{query} du lịch trải nghiệm thực tế Vlog"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        results = []
        for item in data.get("videos", [])[:3]:
            link = item.get("link", "")
            if link and ("youtube.com/watch" in link or "youtu.be" in link):
                results.append(link)
        print(f"[SERPER YouTube] Found {len(results)} videos")
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
    print(f"[CHAT {now_vn}] '{msg[:80]}...' | Session {sid[:8] or 'NONE'}")

    if not GROQ_API_KEY:
        return jsonify({"text": "Lỗi hệ thống: Chưa set GROQ_API_KEY", "images": [], "youtube_links": [], "suggestions": []})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": msg}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4096,
            timeout=90
        )

        raw = completion.choices[0].message.content.strip()
        ai_res = json.loads(raw)

        if not ai_res.get("is_valid", False):
            return jsonify({
                "text": ai_res.get("text", "Không hợp lệ."),
                "images": [], "youtube_links": [], "suggestions": []
            })

        # Lưu vào DB
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (sid, "user", msg, now_vn)
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (sid, "bot", json.dumps(ai_res, ensure_ascii=False), now_vn)
            )
            conn.commit()

        place = msg.strip()
        images = search_serper_images(place)
        youtube = search_serper_youtube(place)

        return jsonify({
            "text": ai_res.get("text", ""),
            "images": images,
            "youtube_links": youtube,
            "suggestions": ai_res.get("suggestions", [])
        })

    except json.JSONDecodeError:
        return jsonify({"text": "Lỗi: AI trả về không phải JSON hợp lệ", "images": [], "youtube_links": [], "suggestions": []})
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "images": [], "youtube_links": [], "suggestions": []})

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    if not sid:
        print("[PDF ERROR] No session_id found")
        return jsonify({"error": "Không tìm thấy session"}), 400

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT role, content, created_at 
                FROM messages 
                WHERE session_id = ? 
                ORDER BY id ASC
            """, (sid,))
            messages = cur.fetchall()

        if not messages:
            print("[PDF] No messages found for session")
            return jsonify({"error": "Chưa có lịch sử chat"}), 404

        pdf = FPDF()
        pdf.add_page()

        # Đăng ký font DejaVuSans.ttf từ thư mục static
        font_path = os.path.join(app.static_folder, "DejaVuSans.ttf")
        if not os.path.exists(font_path):
            print(f"[PDF ERROR] Font not found: {font_path}")
            return jsonify({"error": "Không tìm thấy file font DejaVuSans.ttf"}), 500

        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=12)

        pdf.cell(0, 10, "LỊCH SỬ TRÒ CHUYỆN - VIET NAM TRAVEL AI GUIDE 2026", ln=1, align="C")
        pdf.ln(10)

        for role, content, created_at in messages:
            pdf.set_font("DejaVu", "B", 12)
            pdf.cell(0, 8, f"{role.upper()} - {created_at or 'N/A'}", ln=1)
            pdf.set_font("DejaVu", size=11)

            try:
                data = json.loads(content) if role == "bot" else {"text": content}
                text = data.get("text", content)
            except:
                text = content

            pdf.multi_cell(0, 6, text[:3000])  # giới hạn để tránh lỗi buffer
            pdf.ln(5)

        # Tạo file tạm
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            pdf.output(tmp_file.name)
            tmp_path = tmp_file.name

        response = send_file(
            tmp_path,
            as_attachment=True,
            download_name="lich-su-tro-chuyen.pdf",
            mimetype="application/pdf"
        )

        # Xóa file tạm sau khi gửi
        try:
            os_module.unlink(tmp_path)
        except Exception as unlink_err:
            print(f"[PDF] Không xóa được file tạm: {unlink_err}")

        return response

    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        print(f"[PDF CRITICAL ERROR] {str(e)}")
        return jsonify({"error": f"Lỗi khi tạo PDF: {str(e)}"}), 500

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
