import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# CẤU HÌNH GEMINI (Thay API Key của bạn vào đây)
genai.configure(api_key="KEY_GEMINI_CỦA_BẠN")
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('msg', '')
    if not user_input:
        return jsonify({"text": "Bạn muốn hỏi về địa danh nào?"})

    try:
        # Prompt yêu cầu Gemini trả về cả thông tin và gợi ý tìm kiếm ảnh/video
        prompt = f"""
        Bạn là chuyên gia du lịch. Hãy giới thiệu chi tiết về {user_input} bao gồm:
        1. Lịch sử/Văn hóa.
        2. Các địa điểm đẹp.
        3. Đặc sản nên thử.
        Hãy trình bày bằng HTML đẹp mắt, sử dụng các thẻ <h3>, 📍, <br>.
        """
        response = model.generate_content(prompt)
        ai_text = response.text

        # Vì cào ảnh trực tiếp bị chặn, chúng ta cung cấp Link tìm kiếm an toàn cho người dùng
        search_links = f"""
        <div style='margin-top:20px; border-top:1px solid #ddd; padding-top:10px;'>
            <h4>🔍 Xem thêm hình ảnh & Video:</h4>
            <a href='https://www.google.com/search?tbm=isch&q={user_input}+du+lich' target='_blank' style='color:#d62828'>🖼️ Nhấn để xem bộ sưu tập ảnh {user_input}</a><br>
            <a href='https://www.youtube.com/results?search_query=review+du+lich+{user_input}' target='_blank' style='color:#d62828'>🎥 Nhấn để xem Video Review thực tế</a>
        </div>
        """
        
        full_content = ai_text + search_links
        
        return jsonify({
            "text": full_content,
            "suggestions": [f"Món ngon {user_input}", f"Giá vé {user_input}", f"Mùa nào đẹp tại {user_input}"]
        })

    except Exception as e:
        print(f"Lỗi Gemini: {e}")
        return jsonify({"text": "⚠️ Hệ thống đang quá tải, vui lòng thử lại sau vài giây!"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
