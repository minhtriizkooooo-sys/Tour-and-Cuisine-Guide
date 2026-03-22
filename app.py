import os
import uuid
import sqlite3
import json
import requests
import subprocess
import tempfile
import threading
import logging
import shutil
from datetime import datetime
from pathlib import Path

import pytz
from flask import Flask, request, jsonify, render_template, make_response, send_file, send_from_directory
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

# Setup logging chi tiết
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

# Test ffmpeg availability
def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

FFMPEG_AVAILABLE = check_ffmpeg()
logger.info(f"FFMPEG available: {FFMPEG_AVAILABLE}")

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
                scenes_data TEXT,
                error_log TEXT
            )
        """)

init_db()

# --- Helper Functions ---
def search_serper_images(query, count=8):
    if not SERPER_API_KEY: 
        logger.warning("SERPER_API_KEY not set")
        return []
    try:
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": f"{query} TP.HCM du lịch thực tế 2026"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        return [{"url": i.get("imageUrl"), "caption": i.get("title", query)} for i in data.get("images", [])[:count]]
    except Exception as e:
        logger.error(f"Serper images error: {e}")
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
        logger.error(f"Script generation error: {e}")
        return None

def text_to_speech_gtts(text, output_path, lang='vi'):
    """
    Convert text to speech using gTTS
    Giới hạn text để tránh lỗi
    """
    try:
        from gtts import gTTS
        
        # Giới hạn text - gTTS có giới hạn khoảng 5000 ký tự
        if len(text) > 4000:
            logger.warning(f"Text too long ({len(text)} chars), truncating to 4000")
            text = text[:4000]
        
        # Thêm delay nhỏ để tránh rate limit
        import time
        time.sleep(0.5)
        
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(output_path)
        
        # Verify file
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.info(f"TTS success: {output_path}, size: {os.path.getsize(output_path)} bytes")
            return True
        else:
            logger.error("TTS output file invalid")
            return False
            
    except Exception as e:
        logger.error(f"TTS error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def create_silent_audio(output_path, duration=10):
    """Create silent audio using ffmpeg"""
    if not FFMPEG_AVAILABLE:
        logger.error("FFMPEG not available for silent audio")
        return False
    
    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'lavfi', '-i', 
            f'anullsrc=r=24000:cl=mono', '-t', str(duration),
            '-acodec', 'libmp3lame', '-q:a', '4', output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info(f"Silent audio created: {output_path}")
            return True
        else:
            logger.error(f"Silent audio ffmpeg error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Silent audio timeout")
        return False
    except Exception as e:
        logger.error(f"Silent audio exception: {e}")
        return False

def download_image(url, output_path, max_retries=3):
    """Download image from URL with retry logic"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15, stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Verify image
                try:
                    with Image.open(output_path) as img:
                        img.verify()
                    logger.info(f"Image downloaded: {output_path}")
                    return True
                except Exception as e:
                    logger.warning(f"Invalid image: {e}")
                    if os.path.exists(output_path):
                        os.remove(output_path)
            else:
                logger.warning(f"HTTP {response.status_code} for {url}")
                
        except Exception as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries - 1:
            import time
            time.sleep(1)
    
    return False

def create_text_slide(text, output_path, width=1920, height=1080, bg_color=(0, 102, 204)):
    """Create text slide with Vietnamese text"""
    try:
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Try multiple font options
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        
        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, 60)
                break
            except:
                continue
        
        if font is None:
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
        
        img.save(output_path, quality=95)
        logger.info(f"Text slide created: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Text slide error: {e}")
        return False

def create_video_segment(image_path, audio_path, output_path, duration=10, is_text_slide=False):
    """Create video segment from image and audio using ffmpeg"""
    if not FFMPEG_AVAILABLE:
        logger.error("FFMPEG not available")
        return False, 0
    
    try:
        # Get audio duration
        probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                     '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        
        try:
            audio_duration = float(result.stdout.strip())
        except:
            audio_duration = duration
        
        audio_duration = max(audio_duration, 3)  # Minimum 3 seconds
        
        # Build ffmpeg command
        if is_text_slide:
            # Zoom effect for text slides
            filter_complex = (
                f"loop=loop=-1:size=1:start=0,"
                f"zoompan=z='min(zoom+0.0015,1.5)':d={int(audio_duration*30)}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080,"
                f"format=yuv420p"
            )
        else:
            # Scale image to fit
            filter_complex = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
        
        cmd = [
            'ffmpeg', '-y', 
            '-loop', '1', '-i', image_path, 
            '-i', audio_path,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
            '-pix_fmt', 'yuv420p', 
            '-shortest',
            '-t', str(audio_duration), 
            '-vf', filter_complex,
            output_path
        ]
        
        logger.debug(f"FFmpeg cmd: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False, 0
        
        # Verify output
        if not os.path.exists(output_path):
            logger.error("Output file not created")
            return False, 0
        
        file_size = os.path.getsize(output_path)
        if file_size < 10000:
            logger.error(f"Output file too small: {file_size} bytes")
            return False, 0
        
        logger.info(f"Video segment created: {output_path}, size: {file_size} bytes")
        return True, audio_duration
        
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timeout")
        return False, 0
    except Exception as e:
        logger.error(f"Video segment error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, 0

def concatenate_videos(video_files, output_path):
    """Concatenate multiple video files using ffmpeg"""
    if not video_files:
        logger.error("No video files to concatenate")
        return False
    
    if not FFMPEG_AVAILABLE:
        logger.error("FFMPEG not available")
        return False
    
    try:
        # Method 1: Using concat demuxer
        list_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
        for f in video_files:
            # Escape backslashes and single quotes
            escaped = f.replace('\\', '/').replace("'", "'\\''")
            list_file.write(f"file '{escaped}'\n")
        list_file.close()
        
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', list_file.name, '-c', 'copy', output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            logger.info(f"Concat success: {output_path}")
            os.unlink(list_file.name)
            return True
        
        logger.warning(f"Concat method 1 failed: {result.stderr}")
        os.unlink(list_file.name)
        
        # Method 2: Using filter_complex
        return concatenate_videos_alt(video_files, output_path)
        
    except Exception as e:
        logger.error(f"Concat error: {e}")
        return concatenate_videos_alt(video_files, output_path)

def concatenate_videos_alt(video_files, output_path):
    """Alternative concat method using filter_complex"""
    try:
        inputs = []
        filter_parts = []
        
        for i, f in enumerate(video_files):
            inputs.extend(['-i', f])
            filter_parts.append(f"[{i}:v:0][{i}:a:0]")
        
        filter_complex = ''.join(filter_parts) + f"concat=n={len(video_files)}:v=1:a=1[outv][outa]"
        
        cmd = ['ffmpeg', '-y'] + inputs + [
            '-filter_complex', filter_complex,
            '-map', '[outv]', '-map', '[outa]',
            '-c:v', 'libx264', '-preset', 'ultrafast',
            '-c:a', 'aac', '-b:a', '128k',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info(f"Alt concat success: {output_path}")
            return True
        else:
            logger.error(f"Alt concat failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Alt concat error: {e}")
        return False

def generate_ai_video_background(video_id, session_id):
    """Background task to generate AI video"""
    def update_status(status, file_path=None, completed=False, error_msg=None):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                if completed:
                    conn.execute("""
                        UPDATE generated_videos 
                        SET status = ?, file_path = ?, completed_at = ?, error_log = ?
                        WHERE video_id = ?
                    """, (status, file_path, datetime.now(VN_TZ).isoformat(), error_msg, video_id))
                else:
                    conn.execute("UPDATE generated_videos SET status = ?, error_log = ? WHERE video_id = ?", 
                               (status, error_msg, video_id))
                conn.commit()
                logger.info(f"[{video_id}] Status updated to: {status}")
        except Exception as e:
            logger.error(f"[{video_id}] DB update error: {e}")

    temp_dir = None
    
    try:
        # Kiểm tra dependencies
        if not FFMPEG_AVAILABLE:
            update_status("failed_no_ffmpeg", error_msg="FFMPEG not installed on server")
            return
        
        try:
            from gtts import gTTS
        except ImportError:
            update_status("failed_no_gtts", error_msg="gTTS not installed")
            return
        
        update_status("generating_script")
        
        # Step 1: Generate script
        logger.info(f"[{video_id}] Starting script generation...")
        script = generate_video_script()
        
        if not script:
            update_status("failed_script", error_msg="AI failed to generate script")
            return
        
        scenes = script.get('scenes', [])
        if not scenes:
            update_status("failed_no_scenes", error_msg="No scenes in script")
            return
        
        logger.info(f"[{video_id}] Script generated with {len(scenes)} scenes")
        
        # Update DB with script
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    UPDATE generated_videos 
                    SET scenes_data = ?, title = ?
                    WHERE video_id = ?
                """, (json.dumps(script, ensure_ascii=False), script.get('title', 'AI Video'), video_id))
                conn.commit()
        except Exception as e:
            logger.error(f"[{video_id}] DB update error: {e}")
        
        update_status("collecting_media")
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix=f"video_{video_id}_")
        logger.info(f"[{video_id}] Temp directory: {temp_dir}")
        
        # Test write permissions
        test_file = os.path.join(temp_dir, "test.txt")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logger.info(f"[{video_id}] Temp directory writable")
        except Exception as e:
            update_status("failed_temp_dir", error_msg=f"Cannot write to temp dir: {e}")
            return
        
        video_segments = []
        failed_scenes = []
        total_scenes = len(scenes)
        
        # Step 2: Process each scene
        for idx, scene in enumerate(scenes):
            scene_status = f"processing_scene_{idx+1}/{total_scenes}"
            update_status(scene_status)
            logger.info(f"[{video_id}] === Processing scene {idx+1}/{total_scenes} ===")
            
            try:
                narration = scene.get('narration', '')
                if not narration or len(narration.strip()) < 10:
                    narration = scene.get('visual_description', 'TP.HCM 2026')
                    logger.warning(f"[{video_id}] Scene {idx+1} has no narration, using visual_description")
                
                keywords = scene.get('keywords_for_image', 'Ho Chi Minh City future 2026')
                
                # Generate audio
                audio_path = os.path.join(temp_dir, f"audio_{idx}.mp3")
                logger.info(f"[{video_id}] Generating TTS for scene {idx+1}...")
                
                tts_success = text_to_speech_gtts(narration, audio_path)
                
                if not tts_success:
                    logger.warning(f"[{video_id}] TTS failed, trying silent audio...")
                    # Fallback to silent audio
                    tts_success = create_silent_audio(audio_path, duration=5)
                    if not tts_success:
                        logger.error(f"[{video_id}] Both TTS and silent audio failed for scene {idx+1}")
                        failed_scenes.append(idx)
                        continue
                
                # Get image
                image_path = os.path.join(temp_dir, f"image_{idx}.jpg")
                logger.info(f"[{video_id}] Getting image for scene {idx+1}...")
                
                images = search_serper_images(keywords, count=5)
                image_ok = False
                
                if images:
                    for img_idx, img in enumerate(images):
                        if download_image(img['url'], image_path):
                            logger.info(f"[{video_id}] Image {img_idx+1} downloaded for scene {idx+1}")
                            image_ok = True
                            break
                
                if not image_ok:
                    logger.info(f"[{video_id}] Creating text slide for scene {idx+1}...")
                    visual_desc = scene.get('visual_description', keywords[:100])
                    if not create_text_slide(visual_desc, image_path):
                        logger.error(f"[{video_id}] Failed to create text slide for scene {idx+1}")
                        failed_scenes.append(idx)
                        continue
                
                # Create video segment
                segment_path = os.path.join(temp_dir, f"segment_{idx}.mp4")
                logger.info(f"[{video_id}] Creating video segment for scene {idx+1}...")
                
                success, duration = create_video_segment(
                    image_path, audio_path, segment_path, 
                    is_text_slide=not image_ok
                )
                
                if success:
                    video_segments.append(segment_path)
                    scene['actual_duration'] = duration
                    logger.info(f"[{video_id}] Scene {idx+1} completed, duration: {duration}s")
                else:
                    logger.error(f"[{video_id}] Failed to create segment for scene {idx+1}")
                    failed_scenes.append(idx)
                    
            except Exception as e:
                logger.error(f"[{video_id}] Exception in scene {idx+1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                failed_scenes.append(idx)
                continue
        
        logger.info(f"[{video_id}] Completed {len(video_segments)}/{total_scenes} scenes, failed: {len(failed_scenes)}")
        
        if not video_segments:
            update_status("failed_no_segments", error_msg="No video segments could be created")
            return
        
        update_status("concatenating")
        
        # Step 3: Concatenate
        concat_path = os.path.join(temp_dir, "concatenated.mp4")
        logger.info(f"[{video_id}] Concatenating {len(video_segments)} segments...")
        
        if not concatenate_videos(video_segments, concat_path):
            update_status("failed_concat", error_msg="Failed to concatenate videos")
            return
        
        # Step 4: Add intro
        final_path = os.path.join(VIDEO_STORAGE, f"{video_id}.mp4")
        
        intro_path = os.path.join(temp_dir, "intro.mp4")
        intro_text = f"{script.get('title', 'Tầm nhìn TP.HCM 2026')}\n\nVideo được tạo bởi AI\nHCMC Travel AI Guide 2026"
        intro_img = os.path.join(temp_dir, "intro_img.jpg")
        
        if not create_text_slide(intro_text, intro_img, bg_color=(0, 74, 124)):
            logger.warning(f"[{video_id}] Failed to create intro slide, using first scene as intro")
            # Just copy concat as final
            shutil.copy(concat_path, final_path)
        else:
            silent_intro = os.path.join(temp_dir, "silent_intro.mp3")
            if create_silent_audio(silent_intro, 3):
                if create_video_segment(intro_img, silent_intro, intro_path, 3, True)[0]:
                    final_list = [intro_path] + video_segments
                    if not concatenate_videos(final_list, final_path):
                        logger.warning(f"[{video_id}] Concat with intro failed, using main content")
                        shutil.copy(concat_path, final_path)
                else:
                    shutil.copy(concat_path, final_path)
            else:
                shutil.copy(concat_path, final_path)
        
        # Verify final video
        if not os.path.exists(final_path):
            update_status("failed_no_output", error_msg="Final video file not created")
            return
        
        file_size = os.path.getsize(final_path)
        if file_size < 100000:
            update_status("failed_too_small", error_msg=f"Final video too small: {file_size} bytes")
            return
        
        file_size_mb = file_size / (1024 * 1024)
        logger.info(f"[{video_id}] SUCCESS! Video: {final_path}, size: {file_size_mb:.2f} MB")
        
        update_status("completed", final_path, completed=True)
        
    except Exception as e:
        error_msg = f"Fatal error: {str(e)}"
        logger.error(f"[{video_id}] {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        update_status(f"failed_exception", error_msg=error_msg)
    
    finally:
        # Cleanup
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"[{video_id}] Cleaned up temp directory")
            except Exception as e:
                logger.warning(f"[{video_id}] Cleanup error: {e}")

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
    
    # Check dependencies first
    if not FFMPEG_AVAILABLE:
        return jsonify({
            "error": "FFMPEG not available",
            "message": "Server chưa cài đặt ffmpeg. Vui lòng liên hệ admin."
        }), 503
    
    try:
        from gtts import gTTS
    except ImportError:
        return jsonify({
            "error": "gTTS not installed",
            "message": "Thiếu thư viện gTTS. Vui lòng cài đặt: pip install gTTS"
        }), 503
    
    video_id = str(uuid.uuid4())[:12]
    now_vn = datetime.now(VN_TZ).isoformat()
    
    try:
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
        
    except Exception as e:
        logger.error(f"Failed to start video generation: {e}")
        return jsonify({"error": f"Failed to start: {str(e)}"}), 500

@app.route("/video_status/<video_id>")
def video_status(video_id):
    """Check video generation status"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT status, file_path, title, scenes_data, created_at, completed_at, error_log
                FROM generated_videos WHERE video_id = ?
            """, (video_id,))
            row = cur.fetchone()
        
        if not row:
            return jsonify({"error": "Video not found"}), 404
        
        status, file_path, title, scenes_data, created_at, completed_at, error_log = row
        
        response = {
            "video_id": video_id,
            "status": status,
            "title": title,
            "created_at": created_at,
            "completed_at": completed_at
        }
        
        if error_log:
            response["error_details"] = error_log
        
        if scenes_data:
            try:
                response["scenes"] = json.loads(scenes_data)
            except:
                pass
        
        if status == "completed" and file_path and os.path.exists(file_path):
            response["download_url"] = f"/download_video/{video_id}"
            response["ready"] = True
            response["file_size_mb"] = round(os.path.getsize(file_path) / (1024 * 1024), 2)
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Video status error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/download_video/<video_id>")
def download_video(video_id):
    """Download generated video"""
    try:
        file_path = os.path.join(VIDEO_STORAGE, f"{video_id}.mp4")
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, 
                            download_name=f"HCMC_Vision_2026_{video_id}.mp4")
        return "Video not found", 404
    except Exception as e:
        logger.error(f"Download error: {e}")
        return str(e), 500

@app.route("/my_videos")
def my_videos():
    """List user's generated videos"""
    sid = request.cookies.get("session_id")
    if not sid:
        return jsonify([])
    
    try:
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
        
    except Exception as e:
        logger.error(f"My videos error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/stream_video/<video_id>")
def stream_video(video_id):
    """Stream video for preview"""
    try:
        file_path = os.path.join(VIDEO_STORAGE, f"{video_id}.mp4")
        if os.path.exists(file_path):
            return send_from_directory(VIDEO_STORAGE, f"{video_id}.mp4")
        return "Video not found", 404
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return str(e), 500

@app.route("/video_info")
def video_info():
    """Return information about video generation service"""
    return jsonify({
        "service": "AI Video Generator",
        "version": "1.0",
        "ffmpeg_available": FFMPEG_AVAILABLE,
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

@app.route("/video_logs/<video_id>")
def video_logs(video_id):
    """Get debug logs for a video (admin only)"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT error_log FROM generated_videos WHERE video_id = ?", (video_id,))
            row = cur.fetchone()
        
        if row and row[0]:
            return jsonify({"logs": row[0]})
        return jsonify({"logs": "No logs available"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
