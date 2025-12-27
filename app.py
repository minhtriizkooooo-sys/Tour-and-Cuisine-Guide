import os
import json
from flask import Flask, render_template, request, jsonify
from google import genai

app = Flask(__name__)

# Lấy Key từ Render
keys = [os.environ.get("GEMINI-KEY"), os.environ.get("GEMINI-KEY-1")]
valid_keys = [k.strip() for k in keys if k]
key_index = 0

def get_chat_response(user_input):
    global key_index
    if not valid_keys: return None
    
    try:
        current_key = valid_keys[key_index]
        key_index = (key_index + 1) % len(valid_keys)
        
        # QUAN TRỌNG: Ép sử dụng API version v1 để tránh lỗi 404 v1beta
        client = genai.Client(
            api_key=current_key,
            http_options={'api_version': 'v1'}
        )
        
        prompt = f"Bạn là hướng dẫn viên du lịch. Trả lời về: {user_input}. Trả về JSON: {{\"text\": \"...\", \"video_id\": \"\", \"image_tag\": \"travel\", \"suggestions\": []}}"
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        # Loại bỏ markdown nếu AI trả về nhầm
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Lỗi chi tiết: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    res = get_chat_response(data.get('msg', ''))
    if res: return jsonify(res)
    return jsonify({"text": "AI đang bận, hãy thử lại.", "video_id": "", "image_tag": "vietnam", "suggestions": []})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
