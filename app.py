from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)

# Cấu hình Gemini (Nên dùng biến môi trường trên Render)
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

def search_all_in_one(query):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(user_agent="Mozilla/5.0...").new_page()

            # Tìm Text
            page.goto(f"https://www.google.com/search?q={query}+travel+guide+vietnam")
            texts = page.evaluate('''() => Array.from(document.querySelectorAll('div.VwiC3b')).slice(0,3).map(el => el.innerText).join(' ')''')
            yt_link = page.evaluate('''() => document.querySelector('a[href*="youtube.com"]')?.href || ""''')

            # Tìm Images
            page.goto(f"https://www.google.com/search?q={query}+vietnam+tourism&tbm=isch")
            images = page.evaluate('''() => Array.from(document.querySelectorAll('img')).slice(1,5).map(img => img.src)''')

            browser.close()
            return {"context": texts, "yt": yt_link, "imgs": images}
    except Exception as e:
        print(f"Lỗi cào dữ liệu: {e}")
        return {"context": "", "yt": "", "imgs": []}

@app.route('/')
def index():
    return render_template('index.html')

# CHỈ GIỮ LẠI MỘT HÀM CHAT NÀY
@app.route('/chat', methods=['POST'])
def chat_endpoint(): # Đổi tên hàm thành chat_endpoint để tránh trùng lặp nếu cần
    user_msg = request.json.get('msg', '')
    data = search_all_in_one(user_msg)
    
    prompt = f"""
    Dựa vào thông tin: {data['context']}
    Người dùng hỏi về: {user_msg}
    Hãy đóng vai chuyên gia du lịch trả lời chi tiết về: Lịch sử, Văn hoá, Ẩm thực và Tư vấn du lịch.
    Cuối cùng, hãy đưa ra 2 câu hỏi gợi ý bắt đầu bằng [SUGGESTIONS].
    """
    
    response = model.generate_content(prompt)
    full_text = response.text
    
    # Tách gợi ý
    parts = full_text.split("[SUGGESTIONS]")
    main_text = parts[0]
    suggestions = []
    if len(parts) > 1:
        suggestions = [s.strip("- ").strip() for s in parts[1].split("\n") if s.strip()]

    return jsonify({
        "text": main_text,
        "images": data['imgs'],
        "youtube": data['yt'],
        "suggestions": suggestions[:2]
    })

if __name__ == '__main__':
    # Render yêu cầu port phải lấy từ môi trường
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
