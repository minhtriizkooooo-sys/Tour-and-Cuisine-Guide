import os
import json
from flask import Flask, render_template, request, jsonify
from google import genai

app = Flask(__name__)

keys = [os.environ.get("GEMINI-KEY"), os.environ.get("GEMINI-KEY-1")]
valid_keys = [k.strip() for k in keys if k]
key_index = 0

def get_chat_response(user_input):
    global key_index
    if not valid_keys: return None
    try:
        current_key = valid_keys[key_index]
        key_index = (key_index + 1) % len(valid_keys)
        client = genai.Client(api_key=current_key, http_options={'api_version': 'v1'})
        
        prompt = f"""
        Bạn là hướng dẫn viên du lịch chuyên sâu. Trả lời về: {user_input}.
        Yêu cầu kiến thức về: Lịch sử, Văn hóa, Con người, Ẩm thực đặc sản.
        BẮT BUỘC TRẢ VỀ JSON KHÔNG MÀU (KHÔNG DÙNG ```json):
        {{
          "text": "Nội dung chi tiết (dùng <h3>, <ul>, <li>)",
          "video_id": "Mã ID YouTube (ví dụ: 'Y7vM0_5_S_4')",
          "image_tag": "từ khóa tìm ảnh tiếng Anh",
          "suggestions": ["Câu hỏi tiếp theo 1", "Câu hỏi 2"]
        }}
        """
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"Lỗi AI: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    res = get_chat_response(data.get('msg', ''))
    if res: return jsonify(res)
    return jsonify({"text": "AI đang bận, vui lòng thử lại.", "video_id": "", "image_tag": "travel", "suggestions": []})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
