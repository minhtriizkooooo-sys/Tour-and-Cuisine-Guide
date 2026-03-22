import os
import uuid
import sqlite3
import json
import requests
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import pytz
from flask import Flask, request, jsonify, render_template, make_response, send_file, send_from_directory
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY_TCG")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Video generation settings
VIDEO_STORAGE = "generated_videos"
os.makedirs(VIDEO_STORAGE, exist_ok=True)

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHỈ dành cho: TP.HCM (Thành phố Hồ Chí Minh).
Nếu địa danh, địa điểm, khu vực KHÔNG thuộc TP.HCM → Trả ngay JSON:
{"is_valid": false, "text": "Xin lỗi, tôi chỉ hỗ trợ thông tin du lịch tại TP.HCM thôi nhé!"}

Nếu HỢP LỆ (thuộc TP.HCM): Trả về JSON đầy đủ, phong phú, chi tiết (>2200 từ), dùng markdown ##, ###, ####, danh sách, in nghiêng, **đậm** khi cần. Nội dung bắt buộc có đủ các phần sau:

- ## Lịch sử hình thành và phát triển (từ quá khứ → hiện tại → dự báo đến năm 2026-2030)
- ## Con người, văn hóa, lối sống đặc trưng của cư dân địa phương
- ## Ẩm thực nổi bật (liệt kê 8-12 món đặc trưng + địa chỉ cụ thể + mức giá tham khảo năm 2026)
- ## Gợi ý lịch trình du lịch chi tiết (có 3 lựa chọn: 1 ngày, 2 ngày, 3 ngày – kèm thời gian, phương tiện, chi phí ước tính)
- ## Dự báo & tầm nhìn tương lai phát triển TP.HCM đến 2026-2030 (hạ tầng, đô thị, du lịch, công nghệ, thay đổi cảnh quan…)

Cuối cùng thêm mảng gợi ý câu hỏi tiếp theo:
"suggestions": ["Câu hỏi hay 1", "Câu hỏi hay 2", "Câu hỏi hay 3"]

Trả về **chỉ JSON thuần túy**, không comment, không text thừa:
{
  "is_valid": true,
  "text": "nội dung markdown dài...",
  "suggestions": [...]
}
"""

# Video generation prompt template
VIDEO_SCRIPT_PROMPT = """Bạn là đạo diễn trẻ sáng tạo tại TP.HCM. Tạo kịch bản video 10 phút (khoảng 1500-1800 từ) với chủ đề: "Tầm nhìn của giới trẻ về tương lai TP.HCM 2026-2030".

YÊU CẦU KỊCH BẢN:
- Giọng điệu: Trẻ trung, năng động, lạc quan nhưng thực tế
- Cấu trúc: Mở đầu (1 phút) → 4-5 chương chính (mỗi chương 1.5-2 phút) → Kết luận (1 phút)
- Nội dung: Góc nhìn từ gen Z, millennials về công nghệ, đô thị thông minh, văn hóa, môi trường, startup

TRẢ VỀ JSON với cấu trúc:
{
  "title": "Tiêu đề video hấp dẫn",
  "duration_minutes": 10,
  "scenes": [
    {
      "scene_number": 1,
      "timestamp": "00:00-01:00",
      "narration": "Lời dẫn chi tiết để đọc...",
      "visual_description": "Mô tả hình ảnh cần hiển thị...",
      "keywords_for_image": "từ khóa tìm ảnh hoặc tạo ảnh"
    }
  ],
  "background_music_suggestion": "Thể loại nhạc nền phù hợp",
  "total_word_count": số từ
}
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE,
                session_id TEXT,
                title TEXT,
                status TEXT,
                file_path TEXT,
                created_at TEXT,
                completed_at TEXT,
                scenes_data TEXT
            )
        """)

init_db()

# --- Helper Functions ---
def search_serper_images(query, count=8):
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": f"{query} TP.HCM du lịch thực tế 2026"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        return [{"url": i.get("imageUrl"), "caption": i.get("title", query)} for i in data.get("images", [])[:count]]
    except:
        return []

def search_serper_youtube(query):
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/videos"
        payload = json.dumps({"q": f"{query} TP.HCM du lịch trải nghiệm tiếng Việt 2026"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        return [i.get("link") for i in resp.json().get("videos", []) if "youtube" in i.get("link", "").lower()][:4]
    except:
        return []

def search_serper_future_images():
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": "TP.HCM phát triển tương lai 2026 2027 2030 hình ảnh dự án đô thị thực tế"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        return [{"url": i.get("imageUrl"), "caption": i.get("title", "Tương lai TP.HCM")} for i in data.get("images", [])[:7]]
    except:
        return []

def search_serper_future_youtube():
    if not SERPER_API_KEY: return []
    try:
        url = "https://google.serper.dev/videos"
        payload = json.dumps({"q": "tương lai TP.HCM 2026 2030 phát triển đô thị video tiếng Việt"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        return [i.get("link") for i in resp.json().get("videos", []) if "youtube" in i.get("link", "").lower()][:3]
    except:
        return []

# --- Video Generation Functions ---

def generate_video_script():
    """Generate detailed script using Groq API"""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": VIDEO_SCRIPT_PROMPT}],
            response_format={"type": "json_object"},
            max_tokens=4000
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Script generation error: {e}")
        return None

def text_to_speech_gtts(text, output_path, lang='vi', slow=False):
    """Convert text to speech using gTTS"""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, slow=slow)
        tts.save(output_path)
        return True
    except Exception as e:
        print(f"gTTS error: {e}")
        return create_silent_audio(output_path, duration=10)

def create_silent_audio(output_path, duration=10):
    """Create silent audio as fallback"""
    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 
            f'anullsrc=r=24000:cl=mono', '-t', str(duration),
            '-acodec', 'libmp3lame', '-q:a', '4', output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except Exception as e:
        print(f"Silent audio error: {e}")
        return False

def download_image(url, output_path):
    """Download image from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Image download error: {e}")
    return False

def create_text_slide(text, output_path, width=1920, height=1080, bg_color=(0, 102, 204)):
    """Create text slide with Vietnamese text"""
    try:
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        except:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
            except:
                font = ImageFont.load_default()
        
        # Wrap text
        lines = []
        words = text.split()
        current_line = []
        for word in words:
            current_line.append(word)
            bbox = draw.textbbox((0, 0), ' '.join(current_line), font=font)
            if bbox[2] > width - 100:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))
        
        # Draw text
        y = height // 2 - (len(lines) * 70) // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (width - bbox[2]) // 2
            draw.text((x, y), line, fill=(255, 255, 255), font=font)
            y += 80
        
        img.save(output_path)
        return True
    except Exception as e:
        print(f"Text slide error: {e}")
        return False

def create_video_segment(image_path, audio_path, output_path, duration=10, is_text_slide=False):
    """Create video segment from image and audio"""
    try:
        # Get audio duration using ffprobe
        probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                     '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        audio_duration = float(result.stdout.strip()) if result.returncode == 0 else duration
        
        # Create video from image with audio
        if is_text_slide:
            filter_complex = (
                f"loop=loop=-1:size=1:start=0,"
                f"zoompan=z='min(zoom+0.0015,1.5)':d={int(audio_duration*30)}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080,"
                f"format=yuv420p"
            )
        else:
            filter_complex = "format=yuv420p"
        
        cmd = [
            'ffmpeg', '-y', '-loop', '1', '-i', image_path, '-i', audio_path,
            '-c:v', 'libx264', '-tune', 'stillimage', 
            '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
            '-pix_fmt', 'yuv420p', '-shortest',
            '-t', str(audio_duration), '-vf', filter_complex,
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        return True, audio_duration
    except Exception as e:
        print(f"Video segment error: {e}")
        return False, 0

def concatenate_videos(video_files, output_path):
    """Concatenate multiple video files"""
    try:
        list_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        for f in video_files:
            list_file.write(f"file '{f}'\n")
        list_file.close()
        
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', list_file.name, '-c', 'copy', output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        
        os.unlink(list_file.name)
        return True
    except Exception as e:
        print(f"Concatenate error: {e}")
        return False

def generate_ai_video_background(video_id, session_id):
    """Background task to generate AI video"""
    def update_status(status, file_path=None, completed=False):
        with sqlite3.connect(DB_PATH) as conn:
            if completed:
                conn.execute("""
                    UPDATE generated_videos 
                    SET status = ?, file_path = ?, completed_at = ?
                    WHERE video_id = ?
                """, (status, file_path, datetime.now(VN_TZ).isoformat(), video_id))
            else:
                conn.execute("UPDATE generated_videos SET status = ? WHERE video_id = ?", 
                           (status, video_id))
            conn.commit()
    
    try:
        update_status("generating_script")
        
        # Step 1: Generate script
        script = generate_video_script()
        if not script:
            update_status("failed_script")
            return
        
        # Update with scenes data
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                UPDATE generated_videos 
                SET scenes_data = ?, title = ?
                WHERE video_id = ?
            """, (json.dumps(script, ensure_ascii=False), script.get('title', 'AI Video'), video_id))
            conn.commit()
        
        update_status("collecting_media")
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        video_segments = []
        
        scenes = script.get('scenes', [])
        total_scenes = len(scenes)
        
        # Step 2: Process each scene
        for idx, scene in enumerate(scenes):
            update_status(f"processing_scene_{idx+1}/{total_scenes}")
            
            narration = scene.get('narration', '')
            keywords = scene.get('keywords_for_image', 'Ho Chi Minh City future 2026')
            
            # Generate audio
            audio_path = os.path.join(temp_dir, f"audio_{idx}.mp3")
            if not text_to_speech_gtts(narration, audio_path):
                continue
            
            # Try to get image
            image_path = os.path.join(temp_dir, f"image_{idx}.jpg")
            images = search_serper_images(keywords, count=3)
            
            image_ok = False
            if images:
                for img in images:
                    if download_image(img['url'], image_path):
                        image_ok = True
                        break
            
            if not image_ok:
                # Create text slide as fallback
                visual_desc = scene.get('visual_description', 'TP.HCM 2026')
                create_text_slide(visual_desc, image_path)
            
            # Create video segment
            segment_path = os.path.join(temp_dir, f"segment_{idx}.mp4")
            success, duration = create_video_segment(
                image_path, audio_path, segment_path, 
                is_text_slide=not image_ok
            )
            
            if success:
                video_segments.append(segment_path)
                scene['actual_duration'] = duration
        
        if not video_segments:
            update_status("failed_no_segments")
            return
        
        update_status("concatenating")
        
        # Step 3: Concatenate all segments
        concat_path = os.path.join(temp_dir, "concatenated.mp4")
        if not concatenate_videos(video_segments, concat_path):
            update_status("failed_concat")
            return
        
        # Step 4: Add intro
        final_path = os.path.join(VIDEO_STORAGE, f"{video_id}.mp4")
        
        # Create intro
        intro_path = os.path.join(temp_dir, "intro.mp4")
        intro_text = f"{script.get('title', 'Tầm nhìn TP.HCM 2026')}\n\nVideo được tạo bởi AI\nHCMC Travel AI Guide 2026"
        intro_img = os.path.join(temp_dir, "intro_img.jpg")
        create_text_slide(intro_text, intro_img, bg_color=(0, 74, 124))
        
        # 3 second intro
        silent_intro = os.path.join(temp_dir, "silent_intro.mp3")
        create_silent_audio(silent_intro, 3)
        create_video_segment(intro_img, silent_intro, intro_path, 3, True)
        
        # Final concatenate with intro
        final_list = [intro_path] + video_segments
        if not concatenate_videos(final_list, final_path):
            update_status("failed_final")
            return
        
        # Cleanup temp files
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass
        os.rmdir(temp_dir)
        
        update_status("completed", final_path, completed=True)
        
    except Exception as e:
        print(f"Video generation error: {e}")
        update_status(f"failed: {str(e)}")

# --- Routes ---
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
            response_format={"type": "json_object"}
        )
        ai_res = json.loads(completion.choices[0].message.content)

        if ai_res.get("is_valid", False):
            ai_res["images"] = search_serper_images(msg)
            ai_res["youtube_links"] = search_serper_youtube(msg)
            ai_res["future_images"] = search_serper_future_images()
            ai_res["future_youtube_links"] = search_serper_future_youtube()

        now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, now_vn))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_res), now_vn))

        return jsonify(ai_res)

    except Exception as e:
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "is_valid": False})

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()

    formatted_history = []
    for r, c in rows:
        try:
            content = json.loads(c) if r == "bot" else c
        except:
            content = c
        formatted_history.append({"role": r, "content": content})
    return jsonify(formatted_history)

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

    if not rows:
        return "Không có dữ liệu để xuất."

    pdf = FPDF()
    pdf.add_page()

    font_path = os.path.join("static", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=11)
    else:
        pdf.set_font("Arial", size=11)

    now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    pdf.cell(200, 10, txt="LỊCH TRÌNH & THÔNG TIN DU LỊCH TP.HCM 2026", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Xuất lúc: {now_vn} (Giờ Việt Nam)", ln=True, align='C')
    pdf.ln(12)

    for role, content in rows:
        label = "BẠN: " if role == "user" else "AI: "
        if role == "bot":
            try:
                data = json.loads(content)
                text = data.get("text", "")
                pdf.multi_cell(0, 8, txt=f"{label}\n{text}\n")
            except:
                pdf.multi_cell(0, 8, txt=f"{label}{content}\n")
        else:
            pdf.multi_cell(0, 8, txt=f"{label}{content}\n")
        pdf.ln(6)

    path = f"history_{sid[:12]}.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

# --- Video Generation Routes ---

@app.route("/generate_video", methods=["POST"])
def generate_video():
    """Start AI video generation"""
    sid = request.cookies.get("session_id")
    if not sid:
        sid = str(uuid.uuid4())
    
    video_id = str(uuid.uuid4())[:12]
    now_vn = datetime.now(VN_TZ).isoformat()
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO generated_videos (video_id, session_id, title, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (video_id, sid, "Đang tạo...", "queued", now_vn))
        conn.commit()
    
    # Start background generation
    thread = threading.Thread(
        target=generate_ai_video_background,
        args=(video_id, sid)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "video_id": video_id,
        "status": "queued",
        "message": "Video đang được tạo, vui lòng đợi 5-10 phút..."
    })

@app.route("/video_status/<video_id>")
def video_status(video_id):
    """Check video generation status"""
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT status, file_path, title, scenes_data, created_at, completed_at
            FROM generated_videos WHERE video_id = ?
        """, (video_id,))
        row = cur.fetchone()
    
    if not row:
        return jsonify({"error": "Video not found"}), 404
    
    status, file_path, title, scenes_data, created_at, completed_at = row
    
    response = {
        "video_id": video_id,
        "status": status,
        "title": title,
        "created_at": created_at,
        "completed_at": completed_at
    }
    
    if scenes_data:
        try:
            response["scenes"] = json.loads(scenes_data)
        except:
            pass
    
    if status == "completed" and file_path and os.path.exists(file_path):
        response["download_url"] = f"/download_video/{video_id}"
        response["ready"] = True
    
    return jsonify(response)

@app.route("/download_video/<video_id>")
def download_video(video_id):
    """Download generated video"""
    file_path = os.path.join(VIDEO_STORAGE, f"{video_id}.mp4")
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, 
                        download_name=f"HCMC_Vision_2026_{video_id}.mp4")
    return "Video not found", 404

@app.route("/my_videos")
def my_videos():
    """List user's generated videos"""
    sid = request.cookies.get("session_id")
    if not sid:
        return jsonify([])
    
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT video_id, title, status, created_at, completed_at
            FROM generated_videos WHERE session_id = ?
            ORDER BY created_at DESC
        """, (sid,))
        rows = cur.fetchall()
    
    videos = []
    for row in rows:
        videos.append({
            "video_id": row[0],
            "title": row[1],
            "status": row[2],
            "created_at": row[3],
            "completed_at": row[4],
            "ready": row[2] == "completed"
        })
    
    return jsonify(videos)

@app.route("/stream_video/<video_id>")
def stream_video(video_id):
    """Stream video for preview"""
    file_path = os.path.join(VIDEO_STORAGE, f"{video_id}.mp4")
    if os.path.exists(file_path):
        return send_from_directory(VIDEO_STORAGE, f"{video_id}.mp4")
    return "Video not found", 404

@app.route("/video_info")
def video_info():
    """Return information about video generation service"""
    return jsonify({
        "service": "AI Video Generator",
        "version": "1.0",
        "capabilities": [
            "10-minute video generation",
            "Vietnamese text-to-speech",
            "AI script writing with Groq",
            "Image collection from multiple sources",
            "1080p video rendering with transitions"
        ],
        "estimated_time": "5-10 minutes",
        "topic": "Tầm nhìn của giới trẻ về tương lai TP.HCM 2026-2030"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
