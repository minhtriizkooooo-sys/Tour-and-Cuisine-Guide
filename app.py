import os
import json
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Cấu hình Key luân phiên
keys = [os.environ.get("GEMINI-KEY"), os.environ.get("GEMINI-KEY-1")]
valid_keys = [k.strip() for k in keys if k]
key_index = 0

def get_chat_response(user_input):
    global key_index
    if not valid_keys: return {"error": "No API Key found"}
    
    try:
        current_key = valid_keys[key_index]
        key_index = (key_index + 1) % len(valid_keys)
        
        genai.configure(api_key=current_key)
        # Sử dụng cấu hình tối giản nhất để tránh lỗi 404
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
        Bạn là hướng dẫn viên du lịch chuyên nghiệp. Trả lời về: {user_input}.
        BẮT BUỘC trả về định dạng JSON (không kèm markdown):
        {{
          "text": "Nội dung trả lời chi tiết (dùng <h3>, <ul>, <li>)",
          "video_id": "Mã ID YouTube (ví dụ: 'Y7vM0_5_S_4')",
          "image_tag": "vietnam travel",
          "suggestions": ["Câu hỏi 1", "Câu hỏi 2", "Câu hỏi 3"]
        }}
        """
        
        response = model.generate_content(prompt)
        # Bóc tách JSON an toàn
        raw_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(raw_text)
    except Exception as e:
        print(f"Error detail: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    res = get_chat_response(data.get('msg', ''))
    if res:
        return jsonify(res)
    return jsonify({
        "text": "Hệ thống đang bảo trì API, vui lòng thử lại sau.",
        "video_id": "", "image_tag": "travel", "suggestions": ["Hà Nội", "Đà Nẵng"]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
