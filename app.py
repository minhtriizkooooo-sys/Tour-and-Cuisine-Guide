import os
import uuid
import sqlite3
import json
import requests
import sys
import traceback
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

# DEBUG STARTUP - Phải thấy trong log Render lúc boot
print(f"[STARTUP DEBUG] App booting at {datetime.now(VN_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
print("PYTHON PATH:", sys.executable)
print("GROQ_API_KEY_TCG in os.environ?", "YES" if "GROQ_API_KEY_TCG" in os.environ else "NO - VAR NOT SET ON RENDER")
print("GROQ_API_KEY_TCG prefix:", (os.environ.get("GROQ_API_KEY_TCG") or "NONE")[:10] + "...")
print("GROQ_API_KEY prefix:", (os.environ.get("GROQ_API_KEY") or "NONE")[:10] + "...")
print("FINAL GROQ_API_KEY prefix:", GROQ_API_KEY[:10] + "..." if GROQ_API_KEY else "EMPTY KEY - ALL API CALLS WILL FAIL")
print("SERPER_API_KEY prefix:", SERPER_API_KEY[:10] + "..." if SERPER_API_KEY else "NONE")

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
        print("[SERPER DEBUG] SERPER_API_KEY missing")
        return []
    # ... (giữ nguyên phần còn lại của hàm search_serper như code cũ của bạn)

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

    now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    print(f"[CHAT {now_vn}] REQUEST RECEIVED: '{msg[:80]}...' | Session: {sid[:8] if sid else 'NONE'}...")
    print(f"[CHAT KEY] Using prefix: {GROQ_API_KEY[:10] + '...' if GROQ_API_KEY else 'EMPTY KEY - FAIL IMMEDIATELY'}")

    if not GROQ_API_KEY:
        print("[CHAT ERROR] NO GROQ KEY SET - CHECK RENDER ENV VARS")
        return jsonify({"text": "Lỗi hệ thống: GROQ_API_KEY chưa được set trong Environment Variables trên Render. Hãy kiểm tra và redeploy.", "images": [], "youtube_links": []})

    client = Groq(api_key=GROQ_API_KEY)

    try:
        print("[CHAT GROQ] Calling llama-3.1-8b-instant (light model for test)...")
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=1200,
            timeout=120
        )
        raw = completion.choices[0].message.content
        print(f"[CHAT GROQ SUCCESS] Length: {len(raw)} | Preview: {raw[:150]}...")
        ai_res = json.loads(raw)
        # ... (phần xử lý images, videos, save db, return data giữ nguyên như code cũ của bạn)

    except AuthenticationError as e:
        print(f"[CHAT AUTH ERROR] 401 Invalid key: {str(e)}")
        return jsonify({"text": "Lỗi: Key Groq không hợp lệ (401). Tạo key mới tại https://console.groq.com/keys.", "images": [], "youtube_links": []})
    except RateLimitError as e:
        print(f"[CHAT RATE LIMIT] 429: {str(e)}")
        return jsonify({"text": "Lỗi: Hết quota Groq free tier (429). Đợi reset (thường 1-24h) hoặc upgrade tier.", "images": [], "youtube_links": []})
    except APITimeoutError as e:
        print(f"[CHAT TIMEOUT] {str(e)}")
        return jsonify({"text": "Lỗi: Groq timeout hoặc chậm. Thử lại sau vài phút.", "images": [], "youtube_links": []})
    except Exception as e:
        print(f"[CHAT CRITICAL] {type(e).__name__}: {str(e)}")
        traceback.print_exc(file=sys.stdout)
        return jsonify({"text": f"Lỗi Groq: {str(e)}. Xem log Render chi tiết.", "images": [], "youtube_links": []})

# Giữ nguyên các route /history, /export_pdf, /clear_history như code cũ của bạn

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
