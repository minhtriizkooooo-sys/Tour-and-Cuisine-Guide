import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Cấu hình API Key (Lấy từ biến môi trường trên Render hoặc dán trực tiếp nếu test)
API_KEY = os.environ.get("GEMINI_API_KEY") 
genai.configure(api_key=API_KEY)

# Sử dụng model gemini-1.5-flash
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', method=['POST'])
def chat():
    user_msg = request.json.get("msg")
    if not user_msg:
        return jsonify({"text": "Bạn chưa nhập câu hỏi.", "suggestions": []})

    try:
        # Gọi Gemini AI trả về định dạng mong muốn
        prompt = f"""
        Bạn là một hướng dẫn viên du lịch chuyên nghiệp. 
        Trả lời câu hỏi sau của khách: "{user_msg}"
        
        Yêu cầu trả lời:
        1. Ngôn ngữ: Tiếng Việt.
        2. Cung cấp: Lịch sử, văn hóa, ẩm thực và con người tại địa điểm này.
        3. Kết quả trả về gồm:
           - Nội dung chi tiết.
           - 3 câu hỏi gợi ý ngắn gọn.
           - 1 từ khóa tiếng Anh để tìm ảnh (ví dụ: 'Hanoi street food').
        """

        response = model.generate_content(prompt)
        full_text = response.text

        # Tách gợi ý (giả định AI trả về cuối bài)
        # Để đơn giản, tôi sẽ giả lập phần tách này
        return jsonify({
            "text": full_text,
            "image_tag": "travel,culture",
            "suggestions": ["Tìm món ăn ngon", "Lịch sử nơi này", "Địa điểm gần đây"],
            "video_id": "" 
        })

    except Exception as e:
        print(f"Lỗi hệ thống: {str(e)}")
        return jsonify({
            "text": f"AI đang bận một chút, bạn thử lại nhé! (Chi tiết: {str(e)})",
            "suggestions": []
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
