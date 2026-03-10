import os
import uuid
import sqlite3
import json
import sys
import traceback
import requests
from datetime import datetime
import pytz
from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
from groq import Groq, AuthenticationError, RateLimitError, APITimeoutError, GroqError

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY_TCG") or os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# DEBUG
print(f"[STARTUP] {datetime.now(VN_TZ)} | GROQ key: {'YES' if GROQ_API_KEY else 'NO'} | SERPER: {'YES' if SERPER_API_KEY else 'NO'}")

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (bao gồm tất cả quận, huyện, địa danh nổi bật như Bitexco, Landmark 81, Chợ Bến Thành, Phố đi bộ Nguyễn Huệ, Nhà thờ Đức Bà, Bưu điện Thành phố, các tòa nhà cao tầng, khu vui chơi, quán ăn...), Vũng Tàu và Bình Dương.

1. Nếu địa danh KHÔNG thuộc 3 nơi này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ du lịch TP.HCM, Vũng Tàu và Bình Dương. Nếu là địa điểm trong TP.HCM, thử mô tả rõ hơn nhé!"}

2. Nếu HỢP LỆ: Trả JSON với các trường bắt buộc:
{
  "is_valid": true,
  "text": "Nội dung chi tiết bằng tiếng Việt, dài ít nhất 1800 từ, phong phú, có chiều sâu, cấu trúc rõ ràng (dùng heading ##, ###), bao gồm đầy đủ:
  - Lịch sử hình thành, phát triển qua các giai đoạn (thuộc địa, chiến tranh, đổi mới), sự kiện nổi bật, nhân vật lịch sử, ảnh hưởng đến hiện đại.
  - Văn hóa đặc trưng: lễ hội, phong tục, di sản, nghệ thuật dân gian, giá trị cốt lõi.
  - Con người địa phương: tính cách, lối sống, thói quen, tương tác với du khách, câu chuyện thực tế, sự khác biệt thế hệ.
  - Ẩm thực nổi bật: món đặc sản, nguồn gốc, nguyên liệu, cách chế biến chi tiết, địa chỉ quán ngon (tên + địa chỉ cụ thể + giá tham khảo), mẹo ăn, theo mùa.
  - Gợi ý du lịch chi tiết: check-in gần (khoảng cách, thời gian), hoạt động trải nghiệm, lộ trình 1-3 ngày (giờ cụ thể), lưu ý thời tiết/an toàn/chi phí/giờ mở cửa, mẹo tiết kiệm, hoạt động theo mùa, chỗ ít người biết.",
  "suggestions": ["3 câu hỏi gợi ý bằng tiếng Việt, liên quan sâu đến địa danh, mỗi câu là một string"]
}

Chỉ trả về JSON thuần túy, không có text thừa, không markdown ngoài JSON."""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")

init_db()

def search_serper_images(query):
    """Tìm ảnh bằng Serper.dev (Google Images JSON)"""
    if not SERPER_API_KEY:
        print("[SERPER] Missing API key → skip images")
        return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": query + " Việt Nam thực tế du lịch"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        data = response.json()
        results = []
        for item in data.get("images", [])[:6]:  # lấy tối đa 6 ảnh
            if "imageUrl" in item and item.get("imageUrl", "").startswith("http"):
                results.append({
                    "url": item["imageUrl"],
                    "caption": item.get("title", query)[:80]
                })
        print(f"[SERPER Images] Found {len(results)} images for '{query}'")
        return results
    except Exception as e:
        print(f"[SERPER Images ERROR] {str(e)}")
        return []

def search_serper_youtube(query):
    """Tìm video YouTube bằng Serper"""
    if not SERPER_API_KEY:
        return []
    try:
        url = "https://google.serper.dev/videos"
        payload = json.dumps({"q": query + " du lịch trải nghiệm thực tế"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        data = response.json()
        results = []
        for item in data.get("videos", [])[:3]:  # lấy 3 video
            link = item.get("link", "")
            if "youtube.com/watch" in link or "youtu.be" in link:
                results.append(link)
        print(f"[SERPER YouTube] Found {len(results)} videos")
        return results
    except Exception as e:
        print(f"[SERPER Video ERROR] {str(e)}")
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
        return jsonify({"text": "Lỗi: Chưa set GROQ_API_KEY trên Render → kiểm tra Env Vars", "images": [], "youtube_links": [], "suggestions": []})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.1-70b-versatile",   # Nâng lên model mạnh hơn để text dài, chi tiết (hoặc giữ 8b nếu quota hạn chế)
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": msg}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4096,          # tăng để đủ >1800 từ
            timeout=90
        )

        raw = completion.choices[0].message.content.strip()
        ai_res = json.loads(raw)

        if not ai_res.get("is_valid", False):
            return jsonify({
                "text": ai_res.get("text", "Không hợp lệ."),
                "images": [], "youtube_links": [], "suggestions": []
            })

        # Tìm ảnh + video dựa trên msg (hoặc từ ai_res nếu bạn muốn AI trả keyword)
        place_name = msg.strip().split()[-1] if len(msg.split()) > 1 else msg  # lấy tên địa danh đơn giản
        images = search_serper_images(place_name)
        youtube_links = search_serper_youtube(place_name)

        return jsonify({
            "text": ai_res.get("text", ""),
            "images": images,
            "youtube_links": youtube_links,
            "suggestions": ai_res.get("suggestions", [])
        })

    except json.JSONDecodeError:
        return jsonify({"text": "Lỗi: AI trả về không phải JSON. Thử lại nhé!", "images": [], "youtube_links": [], "suggestions": []})

    except AuthenticationError:
        return jsonify({"text": "Lỗi 401: GROQ key không hợp lệ. Kiểm tra https://console.groq.com/keys", ...})
    except RateLimitError:
        return jsonify({"text": "429: Hết quota Groq. Đợi reset hoặc nâng cấp.", ...})
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "images": [], "youtube_links": [], "suggestions": []})

# Thêm các route /history, /export_pdf, /clear_history nếu bạn đã có trước đó
# Ví dụ route history đơn giản:
@app.route("/history")
def history():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
    return jsonify([{"role": r[0], "content": json.loads(r[1]) if r[0]=="bot" else r[1]} for r in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
