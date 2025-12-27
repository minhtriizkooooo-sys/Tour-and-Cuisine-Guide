import os
import json
from flask import Flask, render_template, request, jsonify
# Chuyển sang dùng google-genai (thư viện mới nhất của Google)
from google import genai 

app = Flask(__name__)

# Cấu hình Key luân phiên
keys = [os.environ.get("GEMINI-KEY"), os.environ.get("GEMINI-KEY-1")]
valid_keys = [k.strip() for k in keys if k]
key_index = 0

def get_chat_response(user_input):
    global key_index
    if not valid_keys:
        return {"error": "Không tìm thấy API Key trong biến môi trường"}
    
    try:
        # Chọn Key luân phiên
        current_key = valid_keys[key_index]
        key_index = (key_index + 1) % len(valid_keys)
        
        # Khởi tạo Client theo chuẩn mới
        client = genai.Client(api_key=current_key)
        
        prompt = f"""
        Bạn là hướng dẫn viên du lịch chuyên nghiệp. Trả lời về: {user_input}.
        Yêu cầu trả về JSON thuần túy (KHÔNG được bao quanh bởi ```json):
        {{
          "text": "Nội dung trả lời chi tiết (dùng <h3>, <ul>, <li>)",
          "video_id": "Mã ID YouTube thực tế liên quan",
          "image_tag": "từ khóa tìm ảnh tiếng Anh",
          "suggestions": ["Gợi ý 1", "Gợi ý 2", "Gợi ý 3"]
        }}
        """
        
        # Gọi API theo cấu trúc mới nhất
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        
        # Chuyển đổi văn bản sang JSON
        return json.loads(response.text)
        
    except Exception as e:
        print(f"Lỗi chi tiết: {str(e)}")
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
    
    # Trường hợp lỗi, trả về dữ liệu mặc định để Web không bị đứng
    return jsonify({
        "text": "Hệ thống AI đang phản hồi chậm hoặc lỗi Key. Bạn vui lòng thử lại sau giây lát!",
        "video_id": "", 
        "image_tag": "vietnam-travel", 
        "suggestions": ["Hà Nội", "Hội An", "Phú Quốc"]
    })

if __name__ == '__main__':
    # Render yêu cầu port phải lấy từ biến môi trường
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
