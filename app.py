import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Lấy API Key từ Render (Thử cả 2 biến bạn đã đặt)
API_KEY = os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")

if API_KEY:
    genai.configure(api_key=API_KEY)
    # Khởi tạo model chuẩn gemini-1.5-flash
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("CẢNH BÁO: Không tìm thấy GEMINI-KEY trong Environment Variables!")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get("msg")
    
    if not user_msg:
        return jsonify({"text": "Vui lòng nhập nội dung.", "suggestions": []})

    try:
        # Prompt chi tiết để AI trả về đúng yêu cầu du lịch
        prompt = f"""
        Bạn là hướng dẫn viên du lịch chuyên nghiệp tại Việt Nam.
        Người dùng hỏi: {user_msg}
        Hãy trả lời bằng tiếng Việt:
        1. Lịch sử, văn hóa và điểm đặc sắc.
        2. Những món ăn ngon nhất định phải thử.
        3. Tính cách con người địa phương.
        4. Gợi ý 3 câu hỏi tiếp theo ngắn gọn.
        5. Cho 1 từ khóa tiếng Anh để tìm ảnh (ví dụ: 'dalat city').
        """
        
        response = model.generate_content(prompt)
        bot_response = response.text

        # Giả lập tag ảnh từ câu trả lời (hoặc lấy từ dòng cuối nếu bạn muốn xử lý chuỗi)
        return jsonify({
            "text": bot_response,
            "image_tag": "vietnam,travel",
            "suggestions": ["Món ăn đặc sản", "Lễ hội tiêu biểu", "Cách di chuyển"],
            "video_id": "" 
        })

    except Exception as e:
        print(f"Lỗi hệ thống: {str(e)}")
        return jsonify({
            "text": "Hệ thống AI đang quá tải hoặc Key của bạn bị lỗi. Hãy kiểm tra lại API Key trên Render.",
            "suggestions": []
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
