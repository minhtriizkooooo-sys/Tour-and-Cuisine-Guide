from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)

# Cấu hình Gemini lấy từ Environment Variable của Koyeb
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

def search_all_in_one(query):
    try:
        with sync_playwright() as p:
            # THÊM CÁC ARGUMENTS NÀY ĐỂ CHẠY TRÊN KOYEB/RENDER KHÔNG LỖI
            browser = p.chromium.launch(
                headless=True, 
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Tìm kiếm thông tin
            search_url = f"https://www.google.com/search?q={query}+lịch+sử+văn+hoá+ẩm+thực+du+lịch"
            page.goto(search_url, timeout=60000) # Đợi tối đa 60s
            
            # Lấy tóm tắt văn bản
            texts = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('div.VwiC3b')).slice(0,3).map(el => el.innerText).join(' ');
            }''')
            
            # Lấy link YouTube đầu tiên
            yt_link = page.evaluate('''() => {
                const link = document.querySelector('a[href*="youtube.com"]');
                return link ? link.href : "";
            }''')

            # Tìm hình ảnh (Chuyển sang tab ảnh)
            img_url = f"https://www.google.com/search?q={query}+vietnam+travel+photography&tbm=isch"
            page.goto(img_url, timeout=60000)
            images = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('img'))
                    .slice(1, 6)
                    .map(img => img.src)
                    .filter(src => src.startsWith('http'));
            }''')

            browser.close()
            return {"context": texts, "yt": yt_link, "imgs": images}
    except Exception as e:
        print(f"Lỗi Playwright: {e}")
        return {"context": "Không thể lấy dữ liệu thời gian thực.", "yt": "", "imgs": []}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        user_msg = request.json.get('msg', '')
        if not user_msg:
            return jsonify({"text": "Bạn chưa nhập câu hỏi."})

        # 1. Tìm dữ liệu thực tế
        data = search_all_in_one(user_msg)
        
        # 2. Tạo Prompt cho AI
        prompt = f"""
        Bạn là hướng dẫn viên du lịch chuyên nghiệp của 'Vietnam Travel AI'.
        Dựa vào dữ liệu tìm kiếm: {data['context']}
        Người dùng hỏi về địa danh: {user_msg}

        Hãy trình bày theo cấu trúc:
        - Lịch sử & Con người địa phương.
        - Văn hoá đặc sắc & Cảnh quan.
        - Ẩm thực phải thử.
        - Lời khuyên du lịch (thời điểm, phương tiện).

        Cuối cùng, hãy đưa ra đúng 2 câu hỏi gợi ý liên quan đến địa danh này, để trong dấu ngoặc vuông như sau:
        [SUGGESTIONS]
        - Đặc sản nào ở đây mua về làm quà tốt nhất?
        - Chi phí du lịch tự túc ở đây khoảng bao nhiêu?
        """
        
        response = model.generate_content(prompt)
        full_text = response.text
        
        # 3. Tách nội dung và gợi ý
        parts = full_text.split("[SUGGESTIONS]")
        main_text = parts[0]
        suggestions = []
        if len(parts) > 1:
            suggestions = [s.strip("- ").strip() for s in parts[1].split("\n") if s.strip()]

        return jsonify({
            "text": main_content if 'main_content' in locals() else main_text,
            "images": data['imgs'],
            "youtube": data['yt'],
            "suggestions": suggestions[:2]
        })
    except Exception as e:
        print(f"Lỗi xử lý Chat: {e}")
        return jsonify({"text": "Xin lỗi, AI đang bận xử lý. Vui lòng thử lại!"})

if __name__ == '__main__':
    # Koyeb/Render yêu cầu chạy trên host 0.0.0.0
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
