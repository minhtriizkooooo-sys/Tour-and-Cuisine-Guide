import os
import json
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Cấu hình danh sách Key luân phiên từ Render Environment
keys = [os.environ.get("GEMINI-KEY"), os.environ.get("GEMINI-KEY-1")]
valid_keys = [k.strip() for k in keys if k]
key_index = 0

def get_next_model():
    global key_index
    if not valid_keys: return None
    current_key = valid_keys[key_index]
    key_index = (key_index + 1) % len(valid_keys)
    genai.configure(api_key=current_key)
    # Lưu ý: 'models/gemini-1.5-flash' là tên chính xác nhất hiện tại
    return genai.GenerativeModel('gemini-1.5-flash')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_data = request.json
    user_input = user_data.get('msg', '')
    
    try:
        model = get_next_model()
        if not model: return jsonify({"error": "No API Key"})

        # Prompt ép AI trả về JSON để frontend dễ xử lý hình ảnh/video
        prompt = f"""
        Bạn là trợ lý du lịch AI chuyên nghiệp tại Việt Nam.
        Yêu cầu cho câu hỏi: "{user_input}"
        Hãy trả lời bằng định dạng JSON nghiêm ngặt sau:
        {{
          "text": "Nội dung trả lời chi tiết, chuyên sâu, dùng tag HTML như <h3>, <ul>, <li> để trình bày.",
          "video_id": "Mã ID video Youtube liên quan (ví dụ: dQw4w9WgXcQ)",
          "image_keyword": "Từ khóa tiếng Anh để tìm ảnh đẹp (ví dụ: 'dalat city' hoặc 'vietnamese food')",
          "suggestions": ["Câu hỏi gợi ý 1", "Câu hỏi gợi ý 2", "Câu hỏi gợi ý 3"]
        }}
        """
        
        response = model.generate_content(prompt)
        # Làm sạch chuỗi JSON nếu AI trả về kèm markdown
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return jsonify(json.loads(clean_json))

    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({
            "text": f"⚠️ Hệ thống đang bận một chút. Bạn hãy thử lại sau 10 giây nhé! (Error: {str(e)})",
            "video_id": "", "image_keyword": "travel", "suggestions": ["Giới thiệu Đà Lạt", "Món ăn Hội An"]
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
