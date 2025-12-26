from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
from playwright.sync_api import sync_playwright
from fpdf import FPDF
import os

app = Flask(__name__)

# Lấy API Key từ biến môi trường của Render
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

def search_all_in_one(query):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        # Tìm Text
        page.goto(f"https://www.google.com/search?q={query}+lịch+sử+văn+hoá+ẩm+thực")
        texts = page.evaluate('''() => Array.from(document.querySelectorAll('div.VwiC3b')).slice(0,3).map(el => el.innerText).join(' ')''')
        yt_link = page.evaluate('''() => document.querySelector('a[href*="youtube.com"]')?.href || ""''')

        # Tìm Images
        page.goto(f"https://www.google.com/search?q={query}+travel+photography&tbm=isch")
        images = page.evaluate('''() => Array.from(document.querySelectorAll('img')).slice(1,5).map(img => img.src)''')

        browser.close()
        return {"context": texts, "yt": yt_link, "imgs": images}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('msg', '')
    data = search_all_in_one(user_msg)
    
    prompt = f"""
    Dữ liệu tìm kiếm: {data['context']}
    Dựa vào dữ liệu trên, hãy viết về địa danh {user_msg}:
    1. Lịch sử phát triển. 
    2. Con người & Văn hoá. 
    3. Ẩm thực đặc sắc. 
    4. Gợi ý du lịch.
    Cuối cùng, đề xuất 2 câu hỏi gợi ý.
    """
    response = model.generate_content(prompt)
    return jsonify({
        "text": response.text,
        "images": data['imgs'],
        "youtube": data['yt']
    })

if __name__ == '__main__':
    app.run(debug=True)
