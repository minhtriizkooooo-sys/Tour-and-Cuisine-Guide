import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Thử lấy Key 1, nếu không có thì lấy Key 2
API_KEY = os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")

if API_KEY:
    genai.configure(api_key=API_KEY)
    # Khởi tạo model chuẩn cho năm 2025
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("CẢNH BÁO: Chưa tìm thấy API Key trên Render!")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get("msg")
    if not user_msg:
        return jsonify({"text": "Bạn chưa nhập tin nhắn.", "suggestions": []})

    try:
        # Prompt tối ưu để AI trả về thông tin du lịch chi tiết
        prompt = f"""
        Bạn là hướng dẫn viên du lịch ảo thông minh. 
        Người dùng hỏi: "{user_msg}"
        Hãy trả lời bằng tiếng Việt:
        1. Thông tin lịch sử, văn hóa, con người và ẩm thực.
        2. Gợi ý 3 hành động tiếp theo cho khách (viết ngắn gọn).
        3. Cuối cùng cho tôi 1 từ khóa tiếng Anh để tìm ảnh liên quan.
        """
        
        response = model.generate_content(prompt)
        content = response.text

        return jsonify({
            "text": content,
            "image_tag": "travel,vietnam", # Có thể xử lý logic tách tag từ content nếu muốn
            "suggestions": ["Khám phá lịch sử", "Tìm món ăn đặc sản", "Chỉ đường đi"],
            "video_id": "" 
        })

    except Exception as e:
        print(f"Lỗi AI: {str(e)}")
        return jsonify({
            "text": "Hiện tại AI đang bảo trì hoặc Key hết hạn mức. Vui lòng thử lại sau!",
            "suggestions": []
        })

if __name__ == '__main__':
    # Render yêu cầu port 10000
    app.run(host='0.0.0.0', port=10000)
