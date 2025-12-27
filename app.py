import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Lấy API Key từ Render
API_KEY = os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")

if API_KEY:
    try:
        genai.configure(api_key=API_KEY)
        # Sử dụng model flash 1.5 ổn định nhất
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("--- Hệ thống AI đã sẵn sàng ---")
    except Exception as e:
        print(f"--- Lỗi cấu hình AI: {str(e)} ---")
else:
    print("--- CẢNH BÁO: Thiếu GEMINI-KEY trên Render ---")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get("msg")
    if not user_msg:
        return jsonify({"text": "Nội dung trống.", "suggestions": []})

    try:
        prompt = f"Bạn là hướng dẫn viên du lịch chuyên nghiệp. Hãy trả lời câu hỏi sau bằng tiếng Việt thật chi tiết: {user_msg}"
        response = model.generate_content(prompt)
        return jsonify({
            "text": response.text,
            "suggestions": ["Món ăn đặc sản", "Lịch sử địa danh", "Chỉ đường đi"],
            "image_tag": "vietnam,travel"
        })
    except Exception as e:
        print(f"Lỗi AI: {str(e)}")
        return jsonify({"text": "AI đang quá tải, vui lòng thử lại sau!", "suggestions": []})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
