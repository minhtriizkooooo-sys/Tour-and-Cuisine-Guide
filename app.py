import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Danh sách các Key lấy từ Render
keys = [os.environ.get("GEMINI-KEY"), os.environ.get("GEMINI-KEY-1")]
# Lọc bỏ các giá trị None nếu bạn chưa điền đủ 2 key
valid_keys = [k.strip() for k in keys if k]

# Biến đếm để luân phiên key
key_index = 0

def get_next_model():
    global key_index
    if not valid_keys:
        return None
    
    # Lấy key theo thứ tự 0 -> 1 -> 0 -> 1
    current_key = valid_keys[key_index]
    key_index = (key_index + 1) % len(valid_keys)
    
    genai.configure(api_key=current_key)
    # Dùng gemini-pro để ổn định nhất, tránh lỗi 404
    return genai.GenerativeModel('gemini-pro')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('msg', '')
    if not user_input:
        return jsonify({"text": "Hãy nhập tên địa danh bạn muốn khám phá!"})

    # Thử gọi AI (nếu lỗi key này sẽ tự đổi sang key kia ở lượt sau)
    try:
        model = get_next_model()
        if not model:
            return jsonify({"text": "❌ Hệ thống chưa cài đặt API Key trên Render!"})

        prompt = f"""
        Bạn là hướng dẫn viên du lịch chuyên nghiệp.
        Yêu cầu: Tư vấn chi tiết về {user_input} (Lịch trình, món ăn, lưu ý).
        Định dạng: Trình bày bằng HTML đẹp (dùng <h3>, 📍, 🍴, <br>).
        """
        
        response = model.generate_content(prompt)
        return jsonify({"text": response.text})

    except Exception as e:
        print(f"Lỗi: {e}")
        # Nếu lỗi 429 (hết lượt) hoặc lỗi key, thử lại lần nữa với key tiếp theo ngay lập tức
        try:
            model = get_next_model()
            response = model.generate_content(prompt)
            return jsonify({"text": response.text})
        except:
            return jsonify({"text": "⚠️ Cả 2 Key đều đang bận hoặc gặp lỗi. Bạn vui lòng đợi 30 giây rồi thử lại nhé!"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
