import os
from flask import Flask, render_template, request, jsonify
from google import genai  # Sử dụng thư viện google-genai mới nhất

app = Flask(__name__)

# Lấy API Key từ Render (Hỗ trợ cả 2 tên biến bạn đã đặt)
API_KEY = os.environ.get("GEMINI-KEY") or os.environ.get("GEMINI-KEY-1")

# Khởi tạo Client AI
client = None
if API_KEY:
    try:
        client = genai.Client(api_key=API_KEY)
        print("--- Kết nối Google GenAI thành công ---")
    except Exception as e:
        print(f"--- Lỗi cấu hình AI: {str(e)} ---")
else:
    print("--- CẢNH BÁO: Thiếu GEMINI-KEY trên Render ---")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    if not client:
        return jsonify({"text": "Hệ thống AI chưa được cấu hình Key.", "suggestions": []})

    data = request.json
    user_msg = data.get("msg")
    if not user_msg:
        return jsonify({"text": "Nội dung trống.", "suggestions": []})

    try:
        # Cách gọi model của thư viện google-genai mới
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"Bạn là hướng dẫn viên du lịch chuyên nghiệp. Hãy trả lời câu hỏi sau bằng tiếng Việt thật chi tiết: {user_msg}"
        )
        
        return jsonify({
            "text": response.text,
            "suggestions": ["Món ăn đặc sản", "Lịch sử địa danh", "Chỉ đường đi"],
            "image_tag": "vietnam,travel"
        })
    except Exception as e:
        print(f"Lỗi AI thực tế: {str(e)}")
        return jsonify({"text": "AI đang bận hoặc Key hết hạn, vui lòng thử lại sau!", "suggestions": []})

if __name__ == '__main__':
    # Render yêu cầu chạy ở port 10000 và host 0.0.0.0
    app.run(host='0.0.0.0', port=10000)
