import os
import uuid
import sqlite3
import json
import sys
import traceback
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

# DEBUG STARTUP
print(f"[STARTUP] App booting at {datetime.now(VN_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
print("PYTHON PATH:", sys.executable)
print("GROQ_API_KEY_TCG exists?", "YES" if "GROQ_API_KEY_TCG" in os.environ else "NO")
print("GROQ_API_KEY_TCG prefix:", (os.environ.get("GROQ_API_KEY_TCG") or "NONE")[:10] + "...")
print("FINAL GROQ_API_KEY prefix:", GROQ_API_KEY[:10] + "..." if GROQ_API_KEY else "EMPTY KEY")

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (bao gồm tất cả quận, huyện, địa danh nổi bật như Bitexco, Landmark 81, Chợ Bến Thành, Phố đi bộ Nguyễn Huệ, Nhà thờ Đức Bà, Bưu điện Thành phố, các tòa nhà cao tầng, khu vui chơi, quán ăn...), Vũng Tàu và Bình Dương.
1. Nếu địa danh KHÔNG thuộc 3 nơi này: Trả JSON {"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ du lịch TP.HCM, Vũng Tàu và Bình Dương. Nếu là địa điểm trong TP.HCM, thử mô tả rõ hơn nhé!"}
2. Nếu HỢP LỆ: Trả JSON {"is_valid": true, "text": "Nội dung chi tiết bằng tiếng Việt, dài >1800 từ, phong phú thông tin, có chiều sâu, cấu trúc rõ ràng và liên quan trực tiếp đến địa danh hỏi: ...", "suggestions": ["3 câu hỏi gợi ý..."]}
Chỉ trả JSON thuần, không thêm text ngoài."""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, created_at TEXT)")

init_db()

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
    print(f"[CHAT {now_vn}] REQUEST: '{msg[:80]}...' | Session: {sid[:8] if sid else 'NONE'}")

    if not GROQ_API_KEY:
        print("[ERROR] GROQ_API_KEY chưa được set trong Environment Variables!")
        return jsonify({
            "text": "Lỗi hệ thống: Chưa cấu hình GROQ_API_KEY trên Render. Vui lòng kiểm tra và redeploy.",
            "images": [], "youtube_links": []
        })

    try:
        print("[GROQ] Khởi tạo client...")
        client = Groq(api_key=GROQ_API_KEY)

        print("[GROQ] Gọi API llama-3.1-8b-instant...")
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": msg}
            ],
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=1200,
            timeout=120
        )

        raw_response = completion.choices[0].message.content.strip()
        print(f"[GROQ OK] Length: {len(raw_response)} | Preview: {raw_response[:150]}...")

        try:
            ai_res = json.loads(raw_response)
        except json.JSONDecodeError:
            print("[ERROR] Groq trả về không phải JSON hợp lệ")
            return jsonify({"text": "Lỗi: AI trả về định dạng không đúng. Thử hỏi lại hoặc báo admin.", "images": [], "youtube_links": []})

        # Phần xử lý images, youtube, suggestions... (bạn bổ sung logic cũ nếu có)
        # Hiện tại trả text + suggestions mẫu
        return jsonify({
            "text": ai_res.get("text", "Không có nội dung trả về từ AI."),
            "images": [],           # thêm logic search nếu cần
            "youtube_links": [],
            "suggestions": ai_res.get("suggestions", [])
        })

    except AuthenticationError:
        return jsonify({"text": "Lỗi: GROQ API key không hợp lệ (401). Kiểm tra lại key.", "images": [], "youtube_links": []})

    except RateLimitError:
        return jsonify({"text": "Hết quota Groq (429). Thử lại sau hoặc nâng cấp plan.", "images": [], "youtube_links": []})

    except APITimeoutError:
        return jsonify({"text": "Groq timeout. Thử lại sau vài phút.", "images": [], "youtube_links": []})

    except GroqError as e:
        print(f"[GROQ ERROR] {type(e).__name__}: {str(e)}")
        return jsonify({"text": f"Lỗi từ Groq: {str(e)}. Thử lại hoặc báo admin.", "images": [], "youtube_links": []})

    except Exception as e:
        print(f"[CRITICAL] {type(e).__name__}: {str(e)}")
        traceback.print_exc(file=sys.stdout)
        return jsonify({
            "text": f"Lỗi hệ thống: {str(e)}. Xem log Render để biết chi tiết.",
            "images": [], "youtube_links": []
        })

# Các route khác (/history, /export_pdf, /clear_history) giữ nguyên nếu bạn đã có

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
