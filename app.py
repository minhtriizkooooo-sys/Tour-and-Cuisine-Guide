import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# LẤY API KEY TỪ RENDER (Khớp chính xác tên GEMINI-KEY)
# Sử dụng .strip() để loại bỏ khoảng trắng dư thừa nếu có
api_key = os.environ.get("GEMINI-KEY")

if api_key:
    # Cấu hình Gemini
    genai.configure(api_key=api_key.strip())
    # Sử dụng bản flash để phản hồi nhanh, tránh lỗi Timeout trên Render
   model = genai.GenerativeModel('gemini-pro')
    print("✅ Đã kết nối thành công với GEMINI-KEY!")
else:
    print("❌ LỖI: Không tìm thấy biến môi trường 'GEMINI-KEY'. Hãy kiểm tra lại Tab Environment trên Render!")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('msg', '')
    if not user_input:
        return jsonify({"text": "Bạn muốn hỏi về địa điểm nào?"})

    # Kiểm tra lại Key trước khi gọi AI
    if not api_key:
        return jsonify({"text": "🤖 Bot chưa có API Key. Hãy kiểm tra lại tên biến 'GEMINI-KEY' trên Render."})

    try:
        # Prompt tối ưu cho gia đình và ẩm thực
        prompt = f"""
        Bạn là hướng dẫn viên du lịch thân thiện. 
        Yêu cầu: Thiết kế tour chi tiết và gợi ý món ăn cho: {user_input}.
        Định dạng trả về: Sử dụng HTML (<h3>, 📍, 🍴, <br>) để nội dung dễ đọc trên ứng dụng.
        """
        
        response = model.generate_content(prompt)
        
        # Trả kết quả về giao diện
        return jsonify({
            "text": response.text
        })

    except Exception as e:
        print(f"Lỗi AI: {e}")
        return jsonify({"text": "⚠️ Hiện tại AI đang bận hoặc API Key chưa kích hoạt. Vui lòng thử lại sau vài giây!"})

if __name__ == '__main__':
    # Render yêu cầu dùng đúng Port từ hệ thống
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

