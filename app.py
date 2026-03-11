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

app = Flask(**name**)
app.secret_key = os.environ.get("SECRET_KEY", "tphcm_ai_travel_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")

DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# ================= PROMPT AI =================

SYSTEM_PROMPT = """
Bạn là chuyên gia du lịch và quy hoạch đô thị TP.HCM.

QUY TẮC BẮT BUỘC

Chỉ xử lý địa danh thuộc TP.HCM.

Nếu địa danh KHÔNG thuộc TP.HCM
Trả JSON:

{
"is_valid": false,
"text": "Xin lỗi, hệ thống AI này chỉ hỗ trợ địa danh thuộc TP.HCM.",
"suggestions":[
"Quận 1 có gì chơi?",
"Du lịch Thủ Đức 2026",
"Quy hoạch Metro TP.HCM"
]
}

Nếu là địa danh TP.HCM

Phải trả lời cực kỳ chi tiết >1800 từ

Trả JSON:

{
"is_valid": true,
"text": "bài viết dài...",
"suggestions":[
"Ăn gì gần địa điểm này?",
"Lịch trình 2 ngày tại đây",
"Metro tương lai khu vực này"
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

# ================= SERPER SEARCH =================

def search_images(query):
if not SERPER_API_KEY:
return []

```
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

def search_future_images(query):
if not SERPER_API_KEY:
return []

```
try:
    url = "https://google.serper.dev/images"

    payload = json.dumps({
        "q": f"quy hoach {query} ho chi minh metro 2030 urban future"
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

# ================= ROUTES =================

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
        future = search_future_images(msg)

        ai["images"] = images
        ai["future_images"] = future

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

# ================= CLEAR =================

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

if **name** == "**main**":
app.run(host="0.0.0.0", port=10000)
