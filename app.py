import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Lấy API Key từ Render (Hỗ trợ cả GEMINI-KEY và GEMINI-KEY-1)
api_key_1 = os.environ.get("GEMINI-KEY")
api_key_2 = os.environ.get("GEMINI-KEY-1")
API_KEY = api_key_1 or api_key_2

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        # Sử dụng tiền tố 'models/' để đảm bảo tính tương thích cao nhất
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        print("--- Kết nối API thành công ---")
    except Exception as e:
        print(f"--- Lỗi cấu hình AI: {str(e)} ---")
else:
    print("--- CẢNH BÁO: Chưa cấu hình biến môi trường GEMINI-KEY trên Render! ---")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get("msg")
    
    if not user_msg:
        return jsonify({"text": "Vui lòng nhập nội dung câu hỏi.", "suggestions": []})

    if not API_KEY:
        return jsonify({"text": "Lỗi: Hệ thống chưa được cấp API Key. Hãy kiểm tra cài đặt Render.", "suggestions": []})

    try:
        # Prompt tối ưu để nhận kết quả chất lượng
        prompt = f"""
        Bạn là hướng dẫn viên du lịch chuyên nghiệp tại Việt Nam.
        Người dùng hỏi: {user_msg}
        Hãy trả lời bằng tiếng Việt:
        1. Lịch sử, văn hóa và điểm đặc sắc.
        2. Những món ăn ngon nhất định phải thử.
        3. Tính cách con người địa phương.
        4. Gợi ý 3 câu hỏi tiếp theo ngắn gọn.
        5. Cho 1 từ khóa tiếng Anh để tìm ảnh (ví dụ: 'hanoi old quarter').
        """
        
        response = model.generate_content(prompt)
        
        # Kiểm tra xem AI có trả về kết quả không
        if response and response.text:
            bot_response = response.text
        else:
            bot_response = "AI không thể trả lời câu hỏi này, vui lòng thử lại."

        return jsonify({
            "text": bot_response,
            "image_tag": "vietnam,travel",
            "suggestions": ["Món ăn đặc sản", "Lễ hội tiêu biểu", "Địa điểm check-in"],
            "video_id": "" 
        })

    except Exception as e:
        error_detail = str(e)
        print(f"Lỗi AI thực tế: {error_detail}") # In ra log của Render để bạn xem
        
        # Thông báo thân thiện cho người dùng
        friendly_msg = "AI đang bận hoặc Key của bạn đã hết hạn mức (Free tier 1500 req/ngày). Hãy thử lại sau 1 phút."
        if "403" in error_detail:
            friendly_msg = "Lỗi: API Key không hợp lệ hoặc bị chặn. Kiểm tra lại Key trên Render."
        
        return jsonify({
            "text": friendly_msg,
            "suggestions": []
        })

if __name__ == '__main__':
    # Render cần port 10000
    app.run(host='0.0.0.0', port=10000)
