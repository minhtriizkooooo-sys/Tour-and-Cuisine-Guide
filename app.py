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
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")

init_db()

def search_serper_images(query):
    if not SERPER_API_KEY:
        print("[SERPER] No API key → skip images")
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
        print(f"[SERPER Images] Found {len(results)} for '{query}'")
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
        print(f"[SERPER YouTube] Found {len(results)}")
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
            "text": "Lỗi hệ thống: Chưa cấu hình GROQ_API_KEY trên Render. Vui lòng kiểm tra Environment Variables.",
            "images": [], "youtube_links": [], "suggestions": []
        })

    try:
        print("[GROQ] Khởi tạo client...")
        client = Groq(api_key=GROQ_API_KEY)

        print("[GROQ] Gọi model...")
        completion = client.chat.completions.create(
            model="llama-3.1-70b-versatile",  # hoặc llama-3.1-8b-instant nếu quota hạn chế
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

        # Tìm ảnh + video
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
        print("[ERROR] Groq trả về không phải JSON hợp lệ")
        return jsonify({
            "text": "Lỗi: AI trả về định dạng không đúng. Thử hỏi lại nhé!",
            "images": [], "youtube_links": [], "suggestions": []
        })

    except AuthenticationError:
        print("[GROQ AUTH ERROR] 401 Invalid key")
        return jsonify({
            "text": "Lỗi: GROQ API key không hợp lệ (401). Kiểm tra lại key tại https://console.groq.com/keys",
            "images": [], "youtube_links": [], "suggestions": []
        })

    except RateLimitError:
        print("[GROQ RATE LIMIT] 429")
        return jsonify({
            "text": "Hết quota Groq (429). Đợi reset quota hoặc nâng cấp plan.",
            "images": [], "youtube_links": [], "suggestions": []
        })

    except APITimeoutError:
        print("[GROQ TIMEOUT]")
        return jsonify({
            "text": "Groq timeout. Thử lại sau vài phút.",
            "images": [], "youtube_links": [], "suggestions": []
        })

    except Exception as e:
        print(f"[CRITICAL ERROR] {type(e).__name__}: {str(e)}")
        traceback.print_exc(file=sys.stdout)
        return jsonify({
            "text": f"Lỗi hệ thống: {str(e)}. Xem log Render để biết chi tiết.",
            "images": [], "youtube_links": [], "suggestions": []
        })

# Nếu bạn đã có các route khác (/history, /export_pdf, /clear_history) thì giữ nguyên
# Ví dụ route history đơn giản (nếu cần):
@app.route("/history")
def get_history():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
    history = []
    for role, content in rows:
        try:
            parsed = json.loads(content) if role == "bot" else content
        except:
            parsed = content
        history.append({"role": role, "content": parsed})
    return jsonify(history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
