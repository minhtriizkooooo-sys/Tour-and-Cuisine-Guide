import os
import json
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Cấu hình danh sách Key luân phiên
keys = [os.environ.get("GEMINI-KEY"), os.environ.get("GEMINI-KEY-1")]
valid_keys = [k.strip() for k in keys if k]
key_index = 0

def get_next_model():
    global key_index
    if not valid_keys: return None
    current_key = valid_keys[key_index]
    key_index = (key_index + 1) % len(valid_keys)
    genai.configure(api_key=current_key)
    
    # Thiết lập hướng dẫn hệ thống để AI trả về JSON
    return genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('msg', '')
    if not user_input: return jsonify({"error": "No message"})

    try:
        model = get_next_model()
        prompt = f"""
        Bạn là hướng dẫn viên du lịch. Hãy trả lời về địa danh: {user_input}.
        BẮT BUỘC trả về định dạng JSON như sau:
        {{
          "text": "Nội dung giới thiệu chi tiết (sử dụng <h3>, <br>)",
          "video_url": "Link video youtube liên quan đến địa danh",
          "suggestions": ["Câu hỏi gợi ý 1", "Câu hỏi gợi ý 2", "Câu hỏi gợi ý 3"]
        }}
        """
        response = model.generate_content(prompt)
        # Chuyển đổi text JSON từ AI thành Dictionary Python
        data = json.loads(response.text)
        return jsonify(data)

    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({
            "text": "⚠️ Hệ thống đang bận. Vui lòng thử lại sau giây lát!",
            "video_url": "",
            "suggestions": ["Đà Lạt có gì đẹp?", "Ẩm thực Hội An", "Tour TPHCM"]
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
