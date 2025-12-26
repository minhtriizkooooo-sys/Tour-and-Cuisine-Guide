from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)

def search_google_all_in_one(query):
    try:
        with sync_playwright() as p:
            # Cấu hình tối ưu cho Render/Koyeb
            browser = p.chromium.launch(
                headless=True, 
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # 1. Cào thông tin và Video
            page.goto(f"https://www.google.com/search?q={query}+du+lịch+lịch+sử+văn+hoá+ẩm+thực", timeout=60000)
            texts = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('div.VwiC3b')).slice(0, 4).map(el => el.innerText).join(' | ');
            }''')
            yt_link = page.evaluate('() => document.querySelector("a[href*=\'youtube.com/watch\']")?.href || ""')

            # 2. Cào hình ảnh
            page.goto(f"https://www.google.com/search?q={query}+vietnam+travel+photography&tbm=isch")
            page.wait_for_timeout(1000)
            imgs = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('img')).slice(1, 6).map(i => i.src).filter(s => s.startsWith('http'));
            }''')

            browser.close()
            return {"context": texts, "yt": yt_link, "imgs": imgs}
    except Exception as e:
        print(f"Lỗi Playwright: {e}")
        return {"context": "", "yt": "", "imgs": []}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    user_msg = request.json.get('msg', '')
    data = search_google_all_in_one(user_msg)
    
    # AI Logic (Thuật toán tự định dạng dữ liệu thông minh)
    parts = data['context'].split('|')
    smart_html = f"<div style='font-family: Arial; line-height: 1.6;'>"
    smart_html += f"<h3 style='color: #0077b6;'>📍 Khám phá: {user_msg}</h3>"
    
    if len(parts) > 0:
        smart_html += f"<p><b>Tổng quan:</b> {parts[0]}</p>"
    if len(parts) > 1:
        smart_html += f"<p><b>🏛️ Văn hóa & Cảnh quan:</b> <ul>"
        for p in parts[1:3]:
            smart_html += f"<li>{p.strip()}</li>"
        smart_html += "</ul></p>"
    
    smart_html += "</div>"

    suggestions = [f"Đặc sản {user_msg}", f"Kinh nghiệm đi {user_msg} tự túc"]

    return jsonify({
        "text": smart_html,
        "images": data['imgs'],
        "youtube": data['yt'],
        "suggestions": suggestions
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
