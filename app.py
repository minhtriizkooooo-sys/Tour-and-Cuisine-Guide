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
app.secret_key = os.environ.get("SECRET_KEY", "tphcm_ai_travel_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") os.environ.get("GROQ_API_KEY_TCG")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# ================= PROMPT AI =================

SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch và quy hoạch đô thị TP.HCM.

Chỉ trả lời địa danh thuộc TP.HCM.

Nếu địa danh không thuộc TP.HCM:
{
"is_valid": false,
"text": "Xin lỗi, hệ thống AI này chỉ hỗ trợ địa danh thuộc TP.HCM.",
"suggestions": [
"Quận 1 có gì chơi?",
"Du lịch Thủ Đức",
"Metro TP.HCM"
]
}

Nếu hợp lệ:
{
"is_valid": true,
"text": "Phân tích chi tiết du lịch + phát triển đô thị + tương lai 2030-2045",
"suggestions": [
"Ăn gì gần đây?",
"Lịch trình tham quan",
"Metro khu vực này"
]
}
"""

# ================= DATABASE =================

def init_db():
with sqlite3.connect(DB_PATH) as conn:
conn.execute("""
CREATE TABLE IF NOT EXISTS messages(
id INTEGER PRIMARY KEY AUTOINCREMENT,
session_id TEXT,
role TEXT,
content TEXT,
created_at TEXT
)
""")

init_db()

# ================= IMAGE SEARCH =================

def search_images(query):

```
if not SERPER_API_KEY:
    return []

try:
    url = "https://google.serper.dev/images"

    payload = json.dumps({
        "q": f"{query} Ho Chi Minh city"
    })

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, data=payload)
    data = r.json()

    return [
        {"url": i["imageUrl"], "caption": i.get("title", query)}
        for i in data.get("images", [])[:8]
    ]

except:
    return []
```

# ================= FUTURE IMAGE =================

def search_future_images(query):

```
if not SERPER_API_KEY:
    return []

try:
    url = "https://google.serper.dev/images"

    payload = json.dumps({
        "q": f"quy hoach {query} ho chi minh skyline 2030 future"
    })

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, data=payload)
    data = r.json()

    return [
        {"url": i["imageUrl"], "caption": "Tầm nhìn đô thị tương lai"}
        for i in data.get("images", [])[:4]
    ]

except:
    return []
```

# ================= FUTURE VIDEO =================

def search_future_videos(query):

```
if not SERPER_API_KEY:
    return []

try:
    url = "https://google.serper.dev/videos"

    payload = json.dumps({
        "q": f"tuong lai {query} ho chi minh metro quy hoach 2030"
    })

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    r = requests.post(url, headers=headers, data=payload)
    data = r.json()

    return [
        v["link"]
        for v in data.get("videos", [])[:3]
    ]

except:
    return []
```

# ================= ROUTE INDEX =================

@app.route("/")
def index():

```
sid = request.cookies.get("session_id") or str(uuid.uuid4())

resp = make_response(render_template("index.html"))

resp.set_cookie(
    "session_id",
    sid,
    httponly=True,
    max_age=31536000
)

return resp
```

# ================= CHAT =================

@app.route("/chat", methods=["POST"])
def chat():

```
sid = request.cookies.get("session_id")

msg = request.json.get("msg", "").strip()

if not msg:
    return jsonify({"error": "Empty message"})

try:

    client = Groq(api_key=GROQ_API_KEY)

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": msg}
        ],
        response_format={"type": "json_object"}
    )

    ai = json.loads(completion.choices[0].message.content)

    if ai.get("is_valid"):

        images = search_images(msg)
        future_images = search_future_images(msg)
        future_videos = search_future_videos(msg)

        ai["images"] = images
        ai["future_images"] = future_images
        ai["future_youtube_links"] = future_videos

    now = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            "INSERT INTO messages (session_id,role,content,created_at) VALUES (?,?,?,?)",
            (sid, "user", msg, now)
        )

        conn.execute(
            "INSERT INTO messages (session_id,role,content,created_at) VALUES (?,?,?,?)",
            (sid, "bot", json.dumps(ai), now)
        )

    return jsonify(ai)

except Exception as e:

    return jsonify({
        "is_valid": False,
        "text": f"Lỗi hệ thống {str(e)}"
    })
```

# ================= HISTORY =================

@app.route("/history")
def history():

```
sid = request.cookies.get("session_id")

with sqlite3.connect(DB_PATH) as conn:

    cur = conn.cursor()

    cur.execute(
        "SELECT role,content FROM messages WHERE session_id=? ORDER BY id",
        (sid,)
    )

    rows = cur.fetchall()

res = []

for r, c in rows:

    try:
        if r == "bot":
            c = json.loads(c)
    except:
        pass

    res.append({
        "role": r,
        "content": c
    })

return jsonify(res)
```

# ================= CLEAR HISTORY =================

@app.route("/clear_history", methods=["POST"])
def clear_history():

```
sid = request.cookies.get("session_id")

with sqlite3.connect(DB_PATH) as conn:

    conn.execute(
        "DELETE FROM messages WHERE session_id=?",
        (sid,)
    )

return jsonify({"status": "ok"})
```

# ================= EXPORT PDF =================

@app.route("/export_pdf")
def export_pdf():

```
sid = request.cookies.get("session_id")

with sqlite3.connect(DB_PATH) as conn:

    cur = conn.cursor()

    cur.execute(
        "SELECT role,content,created_at FROM messages WHERE session_id=? ORDER BY id",
        (sid,)
    )

    rows = cur.fetchall()

pdf = FPDF()
pdf.add_page()

font_path = "static/DejaVuSans.ttf"

pdf.add_font("DejaVu", "", font_path, uni=True)
pdf.set_font("DejaVu", "", 14)

for role, content, time in rows:

    if role == "bot":
        try:
            content = json.loads(content)
            text = content.get("text", "")
        except:
            text = content
    else:
        text = content

    pdf.multi_cell(
        0,
        10,
        f"{role.upper()} {time}\n{text}\n"
    )

path = "chat_history.pdf"
pdf.output(path)

return send_file(path, as_attachment=True)
```

# ================= START =================

if **name** == "main":
app.run(host="0.0.0.0", port=10000)

