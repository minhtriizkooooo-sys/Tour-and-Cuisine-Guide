import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Lấy API Key từ Environment Variable tên là 'gemini-key' mà bạn đã tạo trên Render
api_key = os.environ.get("gemini-key")

if api_key:
    genai.configure(api_key=api_key.strip())
    # Sử dụng bản flash để tốc độ phản hồi nhanh nhất, tránh bị timeout trên Render
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("⚠️ CẢNH BÁO: Chưa tìm thấy biến môi trường 'gemini-key'!")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('msg', '')
    if not user_input:
        return jsonify({"text": "Bạn muốn hỏi về địa danh nào?"})

    if not api_key:
        return jsonify({"text": "⚠️ Hệ thống chưa cấu hình API Key. Vui lòng kiểm tra lại Render Environment."})

    try:
        # Prompt tối ưu để nhận phản hồi nhanh và đẹp
        prompt = f"""
        Bạn là hướng dẫn viên du lịch chuyên nghiệp. Hãy giới thiệu về {user_input}.
        Yêu cầu:
        1. Trình bày bằng HTML (dùng <h3>, 📍, <br>).
        2. Thông tin ngắn gọn về lịch sử, điểm đến và món ăn đặc sản.
        3. Cuối cùng, gợi ý 3 câu hỏi liên quan.
        """
        
        response = model.generate_content(prompt)
        ai_text = response.text

        # Cung cấp link tìm kiếm hình ảnh vì Render chặn cào ảnh trực tiếp
        search_links = f"""
        <div style='margin-top:15px; border-top:1px solid #eee; padding-top:10px;'>
            <p>🔍 <b>Xem thêm:</b> 
            <a href='https://www.google.com/search?tbm=isch&q={user_input}+du+lich' target='_blank' style='color:#007bff'>Ảnh thực tế</a> | 
            <a href='https://www.youtube.com/results?search_query=review+du+lich+{user_input}' target='_blank' style='color:#007bff'>Video Review</a>
            </p>
        </div>
        """
        
        return jsonify({
            "text": ai_text + search_links
        })

    except Exception as e:
        print(f"Lỗi khi gọi Gemini: {e}")
        return jsonify({"text": "⚠️ Xin lỗi, robot đang bận xử lý hoặc API Key gặp lỗi. Bạn thử lại sau nhé!"})

if __name__ == '__main__':
    # Render yêu cầu chạy đúng Port được cấp
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
